import numpy as np
from models import density_model, viscosity_model, andreussi_gas_liquid,\
    colebrook_white_explicit_friction_factor, GRAVITY_CONSTANT,\
    computeGeometricProperties

'''
IN THIS CODE U IS THE SUPERFICIAL VELOCITY:
    U = u * α
'''

def calculate_jacobian_mass(dt, UT, UTold, αT, αTold, P, Pold, dx, nx, dof, 
                            Mpresc, Ppresc, ρrefT, D, DhT=None, SwT=None, Si=None, H=None, fi=None, Pprev=None, Ap_uT=None):
    
    row  = []
    col  = []
    data = []
    
    nphases = αT.shape[1] 
    
    bsize = dof - nphases
    idx   = np.arange(nx, dtype=int) 
    idxαG = idx * bsize + 0
    idxαL = idx * bsize + 1
    idxP  = idx * bsize + nphases
    size  = bsize * nx
    
    αG = αT[:, 0]                 
    αL = αT[:, 1]  
    αTotal = αG + αL
       
    αT = np.zeros((nx, nphases))
    αT[:, 0] = αG #/ αTotal
    αT[:, 1] = αL #/ αTotal
                            
    A = 0.25 * np.pi * D ** 2 # [m]
    ΔV = A * dx
    
    ρG = density_model[0](P*1e5)
    ρGf = 0.5 * (ρG[:-1] + ρG[1:])
    ρGf = np.concatenate(([ρGf[0]], ρGf))
    ρL = density_model[1](P*1e5)
    ρLf = 0.5 * (ρL[:-1] + ρL[1:])
    ρLf = np.concatenate(([ρLf[0]], ρLf))
    
    αG = αT[:, 0]         
    
    Ur = UT[:, 0] - UT[:, 1]
        
    if H is None:
        DhT, SwT, Si, H = computeGeometricProperties(αT, D)
    
    if fi is None:
        μG = viscosity_model[0](P*1e5)
        DhG = DhT[:, 0]        
        
        μGf  = 0.5 * (μG[:-1] + μG[1:])        
        αGf  = 0.5 * (αG[:-1] + αG[1:])        
        DhGf = 0.5 * (DhG[:-1] + DhG[1:])        
        Hf = 0.5 * (H[:-1] + H[1:])        
        μGf  = np.concatenate(([μGf[0]], μGf))        
        αGf  = np.concatenate(([αGf[0]], αGf))       
        DhGf = np.concatenate(([DhGf[0]], DhGf))
        Hf = np.concatenate(([Hf[0]], Hf))
        
        Rei = ρGf * np.abs(Ur) * DhGf / μGf

        fi = andreussi_gas_liquid(
            Rei,
            αGf,
            D,
            1e-5,
            Hf,
            ρLf,
            ρGf,
            np.abs(Ur),
            A * αGf
        )        
        
        τi = 0.5 * fi * ρGf * np.abs(Ur) * Ur   
        sign_τ = [+1, -1]
        UG = UT[:, 0]
        UL = UT[:, 1]
        
        Uother = [UL, UG]
        
    for phase in range(nphases):
        
        idxα = idx * bsize + phase
        
        U = UT[:, phase]
        
        α = αT[:, phase]
        
        Uold = UTold[:, phase]
        αold = αTold[:, phase]
        
        ρref = ρrefT[:, phase]
        
        Dh = DhT[:, phase]
        Sw = SwT[:, phase]
        
        ρ = density_model[phase](P*1e5)
        c = density_model[phase](P*1e5, deriv=True)
        μ = viscosity_model[phase](P*1e5)
        ρold = density_model[phase](Pold*1e5)
        
        ρf = 0.5 * (ρ[:-1] + ρ[1:])
        ρfold = 0.5 * (ρold[:-1] + ρold[1:])
        μf = 0.5 * (μ[:-1] + μ[1:])
        cf = 0.5 * (c[:-1] + c[1:])
        αf = 0.5 * (α[:-1] + α[1:])
        αfold = 0.5 * (αold[:-1] + αold[1:])
        Sif = 0.5 * (Si[:-1] + Si[1:])
        Swf = 0.5 * (Sw[:-1] + Sw[1:])
        Dhf = 0.5 * (Dh[:-1] + Dh[1:])
        ρf = np.concatenate(([ρf[0]], ρf))
        ρfold = np.concatenate(([ρfold[0]], ρfold))
        μf = np.concatenate(([μf[0]], μf))
        cf = np.concatenate(([cf[0]], cf))
        αf = np.concatenate(([αf[0]], αf))
        αfold = np.concatenate(([αfold[0]], αfold))
        Sif = np.concatenate(([Sif[0]], Sif))
        Swf = np.concatenate(([Swf[0]], Swf))
        Dhf = np.concatenate(([Dhf[0]], Dhf))
        
        Rew = ρf * np.abs(U) * Dhf / μf
    
        fw = colebrook_white_explicit_friction_factor(Rew, None, D, absolute_rugosity=1e-5)
        τw = 0.5 * fw * ρf * np.abs(U) * U   
        
        ######################################
        # MOMENTUM CENTRAL NODES
        # Staggered
        Uc = 0.5 * (U[1:] + U[:-1])        
        θ = 0.0 # for now
        g = GRAVITY_CONSTANT         
       
        # create the pressure equation
        Û = np.zeros(nx)
        ΔU = np.zeros(nx)
        # center momentum
        β = np.where(Uc > 0.0, 0.5, -0.5)
        
        if Ap_uT is None:
            Ap_u = np.zeros(nx)
            Ap_u[1:-1] = ρf[1:-1] * αf[1:-1] * ΔV/dt \
                + α[1:-1] * ρ[1:-1] * Uc[1:  ] * A * ((β[1:  ] + 0.5) ) \
                - α[ :-2] * ρ[ :-2] * Uc[ :-1] * A * ((β[ :-1] - 0.5) ) \
                + 0.5 * fw[1:-1] * ρf[1:-1] * np.abs( U[1:-1]) * (Swf[1:-1] / A) * ΔV \
                + 0.5 * fi[1:-1] * ρGf[1:-1] * np.abs(Ur[1:-1]) * (Sif[1:-1] / A) * ΔV
    
            Ap_u[-1] = ρf[-1] * αf[-1] * ΔV/dt * 0.5 \
                + α[-2] * ρ[-2] * U[-1] * A  * \
                - α[-2] * ρ[-2] * Uc[-1] * A * ((β[-1] - 0.5) ) \
                + 0.5 * fw[-1] * ρf[-1] * np.abs( U[-1]) * (Swf[-1] / A) * ΔV * 0.5 \
                + 0.5 * fi[-1] * ρGf[-1] * np.abs(Ur[-1]) * (Sif[-1] / A) * ΔV * 0.5
        else:
            Ap_u = Ap_uT[:, phase]

        ΔP = P - Pprev
        ΔU[1:-1] = - αf[1:-1] * (ΔP[1:-1] - ΔP[:-2]) * 1e5 * A / Ap_u[1:-1]
        ΔU[-1] =   - αf[-1] * (- ΔP[-2]) * 1e5 * A / Ap_u[-1] 
        Ú = U + ΔU
           
#         Û[0] = U[0]
        Û[0] = Mpresc[phase] / (αf[0] * ρf[0] * A)
        Û[1:-1] = \
                   - αf[1:-1] * (P[1:-1] - P[:-2]) * 1e5 * A / Ap_u[1:-1] \
                   - αf[1:-1] * ρf[1:-1] * g * np.cos(θ) * A * (H[1:-1] - H[:-2]) / Ap_u[1:-1] \
                   - α[1:-1] * ρ[1:-1] * Uc[1:  ] * A * ((β[1:  ] - 0.5) * U[2:  ]) / Ap_u[1:-1] \
                   + α[ :-2] * ρ[ :-2] * Uc[ :-1] * A * ((β[ :-1] + 0.5) * U[ :-2]) / Ap_u[1:-1] \
                   + ρfold[1:-1] * αfold[1:-1] * Uold[1:-1] * ΔV/dt / Ap_u[1:-1] \
                   + 0.5 * fi[1:-1] * ρGf[1:-1] * np.abs(Ur[1:-1]) * Uother[phase][1:-1] * (Sif[1:-1] / A) * ΔV / Ap_u[1:-1]
                   
        Û[-1] = \
                   - αf[-1] * (Ppresc  - P[ -2]) * 1e5 * A / Ap_u[  -1] \
                   - αf[-1] * ρf[-1] * g * np.cos(θ) * A * (H[-1] - H[-2]) / Ap_u[  -1] \
                   - α[-2] * ρ[-2] * U[-1] * A * U[-1] / Ap_u[  -1]  \
                   + α[-2] * ρ[-2] * Uc[-1] * A * ((β[-1] + 0.5) * U[-2]) / Ap_u[  -1] \
                   + ρfold[-1] * αfold[-1] * Uold[-1] * ΔV/dt * 0.5 / Ap_u[  -1] \
                   + 0.5 * fi[-1] * ρGf[-1] * np.abs(Ur[-1]) * Uother[phase][-1] * (Sif[-1] / A) * ΔV / Ap_u[  -1]
                   
#         Û = Ú
#         ϕ = 0.9
#         Û = ϕ * Û + (1 - ϕ) * Ú

                       
        ρρ = np.concatenate(([ρ[0]], ρ))
        αα = np.concatenate(([α[0]], α))
        β = np.where(U > 0.0, 0.5, -0.5) 

#         fP = \
#             + (ρ[:-1] * α[:-1] - ρold[:-1] * αold[:-1]) * ΔV/dt \
#             + ((β[1:  ] - 0.5) * ρ[1:  ] * α[1:  ] + (β[1:  ] + 0.5) *  ρ[ :-1]  * α[ :-1]) * Û[1:  ] * A \
#             - ((β[ :-1] - 0.5) * ρ[ :-1] * α[ :-1] + (β[ :-1] + 0.5) * ρρ[ :-2] * αα[ :-2]) * Û[ :-1] * A \
            
        
        # Coeff's            
        ############################
        ##### DERIVATIVES W.R.T α    
        # P -> α[ :-1]
        dRdαP = + (ρ[:-1] ) * ΔV/dt \
                + ((β[1:  ] + 0.5) * ρ[ :-1]) * U[1:  ] * A \
                - ((β[ :-1] - 0.5) * ρ[ :-1]) * U[ :-1] * A
        
        # E -> α[1:  ]  
        dRdαE = + ((β[1:  ] - 0.5) *  ρ[1:  ]) * U[1:  ] * A \
        
        # W -> α[ :-1] 
        dRdαW = - ((β[ :-1] + 0.5) * ρρ[ :-2]) * U[ :-1] * A \

        ############################
        ##### DERIVATIVES W.R.T U    
        # e Û[1:  ] 
        dRdUe = + ((β[1:  ] - 0.5) * ρ[1:  ] * α[1:  ] + (β[1:  ] + 0.5) *  ρ[ :-1]  * α[ :-1]) * A        
        dUedPE = - αf[1:] * (+1) * 1e5 * A / Ap_u[1:]
        dUedPP = - αf[1:] * (-1) * 1e5 * A / Ap_u[1:]
        
        # w Û[1:  ] 
        dRdUw = - ((β[ :-1] - 0.5) * ρ[ :-1] * α[ :-1] + (β[ :-1] + 0.5) * ρρ[ :-2] * αα[ :-2]) * A
        dUwdPP = - αf[1:] * (+1) * 1e5 * A / Ap_u[1:]
        dUwdPW = - αf[1:] * (-1) * 1e5 * A / Ap_u[1:]
        
        ############################
        ##### DERIVATIVES W.R.T P    
        
        dRdρP = + (α[:-1]) * ΔV/dt \
            + ((β[1:  ] + 0.5) * α[ :-1]) * U[1:  ] * A \
            - ((β[ :-1] - 0.5) * α[ :-1]) * U[ :-1] * A
            
        dRdρE = + ((β[1:  ] - 0.5) *  α[1:  ]) * U[1:  ] * A 
        dRdρW = - ((β[ :-1] + 0.5) * αα[ :-2]) * U[ :-1] * A
        
        dρdP = c[:-1] * 1e5 # like this for now
        
        dRdPP = (dRdρP*dρdP + dRdUe*dUedPP + dRdUw*dUwdPP) #/ ρref[:-1]
        dRdPE = (dRdρE*dρdP + dRdUe*dUedPE) #/ ρref[:-1]
        dRdPW = (dRdρW*dρdP + dRdUw*dUwdPW) #/ ρref[:-1]
 
        row  = np.concatenate((row , idxP[:-1])).astype(int)
        col  = np.concatenate((col , idxP[:-1])).astype(int)
        data = np.concatenate((data, dRdPP))
        
        row  = np.concatenate((row , idxP[:-2])).astype(int)
        col  = np.concatenate((col , idxP[:-2] + bsize)).astype(int)
        data = np.concatenate((data, dRdPE[:-1]))
        
        row  = np.concatenate((row , idxP[1:-1])).astype(int)
        col  = np.concatenate((col , idxP[1:-1] - bsize)).astype(int)
        data = np.concatenate((data, dRdPW[1:]))
        
        row  = np.concatenate((row , idxα[:-1])).astype(int)
        col  = np.concatenate((col , idxα[:-1])).astype(int)
        data = np.concatenate((data, dRdαP))
        
        row  = np.concatenate((row , idxα[:-2])).astype(int)
        col  = np.concatenate((col , idxα[:-2] + bsize)).astype(int)
        data = np.concatenate((data, dRdαE[:-1]))
        
        row  = np.concatenate((row , idxα[1:-1])).astype(int)
        col  = np.concatenate((col , idxα[1:-1] - bsize)).astype(int)
        data = np.concatenate((data, dRdαW[1:]))

        
        # Mass        
        #αpresc = 0.5
        #f[-1,phase] = α[-1] - ((β[-1] - 0.5) * αpresc + (β[-1] + 0.5) * α[-2])
#         f[-1,phase] = α[-1] - α[-2]

        row  = np.concatenate((row , idxα[-2:])).astype(int)
        col  = np.concatenate((col , idxα[-2:])).astype(int)
        data = np.concatenate((data, [-1, 1]))


    # pressure ghost    
    #f[ -1, -1] = -(Ppresc - P[-1])
    
    row  = np.concatenate((row , [idxP[-1]])).astype(int)
    col  = np.concatenate((col , [idxP[-1]])).astype(int)
    data = np.concatenate((data, [1]))
        
    #f[:-1, -1] = 1 - αTotal[:-1]
    
    return row, col, data

def calculate_residual_mass(dt, UT, UTold, αT, αTold, P, Pold, dx, nx, dof, 
                            Mpresc, Ppresc, ρrefT, D, DhT=None, SwT=None, Si=None, H=None, fi=None, Pprev=None, Ap_uT=None):
    
    ΔP = P - Pprev
    update_velocities(ΔP, None, dt, UT, UTold, αT, αTold, P, Pold, dx, nx, dof, Mpresc, Ppresc, ρrefT, D, Ap_uT=Ap_uT)
        
    nphases = αT.shape[1] 
    f = np.zeros((nx, dof-nphases))    
    
    αG = αT[:, 0].copy()                
    αL = αT[:, 1].copy()     
    αTotal = αG + αL
       
    αT = np.zeros((nx, nphases))
    αT[:, 0] = αG / αTotal
    αT[:, 1] = αL / αTotal
                            
    A = 0.25 * np.pi * D ** 2 # [m]
    ΔV = A * dx
    
    ρG = density_model[0](P*1e5)
    ρGf = 0.5 * (ρG[:-1] + ρG[1:])
    ρGf = np.concatenate(([ρGf[0]], ρGf))
    ρL = density_model[1](P*1e5)
    ρLf = 0.5 * (ρL[:-1] + ρL[1:])
    ρLf = np.concatenate(([ρLf[0]], ρLf))
    
    αG = αT[:, 0]         
    
    Ur = UT[:, 0] - UT[:, 1]
        
    if H is None:
        DhT, SwT, Si, H = computeGeometricProperties(αT, D)
    
    if fi is None:
        μG = viscosity_model[0](P*1e5)
        DhG = DhT[:, 0]        
        
        μGf  = 0.5 * (μG[:-1] + μG[1:])        
        αGf  = 0.5 * (αG[:-1] + αG[1:])        
        DhGf = 0.5 * (DhG[:-1] + DhG[1:])        
        Hf = 0.5 * (H[:-1] + H[1:])        
        μGf  = np.concatenate(([μGf[0]], μGf))        
        αGf  = np.concatenate(([αGf[0]], αGf))       
        DhGf = np.concatenate(([DhGf[0]], DhGf))
        Hf = np.concatenate(([Hf[0]], Hf))
        
        Rei = ρGf * np.abs(Ur) * DhGf / μGf

        fi = andreussi_gas_liquid(
            Rei,
            αGf,
            D,
            1e-5,
            Hf,
            ρLf,
            ρGf,
            np.abs(Ur),
            A * αGf
        )        
        
        τi = 0.5 * fi * ρGf * np.abs(Ur) * Ur   
        sign_τ = [+1, -1]
        UG = UT[:, 0]
        UL = UT[:, 1]
        
        Uother = [UL, UG]
        
    for phase in range(nphases):
        
        U = UT[:, phase]
        
        α = αT[:, phase]
        
        Uold = UTold[:, phase]
        αold = αTold[:, phase]
        
        ρref = ρrefT[:, phase]
        
        Dh = DhT[:, phase]
        Sw = SwT[:, phase]
        
        ρ = density_model[phase](P*1e5)
        c = density_model[phase](P*1e5, deriv=True)
        μ = viscosity_model[phase](P*1e5)
        ρold = density_model[phase](Pold*1e5)
        
        ρf = 0.5 * (ρ[:-1] + ρ[1:])
        ρfold = 0.5 * (ρold[:-1] + ρold[1:])
        μf = 0.5 * (μ[:-1] + μ[1:])
        cf = 0.5 * (c[:-1] + c[1:])
        αf = 0.5 * (α[:-1] + α[1:])
        αfold = 0.5 * (αold[:-1] + αold[1:])
        Sif = 0.5 * (Si[:-1] + Si[1:])
        Swf = 0.5 * (Sw[:-1] + Sw[1:])
        Dhf = 0.5 * (Dh[:-1] + Dh[1:])
        ρf = np.concatenate(([ρf[0]], ρf))
        ρfold = np.concatenate(([ρfold[0]], ρfold))
        μf = np.concatenate(([μf[0]], μf))
        cf = np.concatenate(([cf[0]], cf))
        αf = np.concatenate(([αf[0]], αf))
        αfold = np.concatenate(([αfold[0]], αfold))
        Sif = np.concatenate(([Sif[0]], Sif))
        Swf = np.concatenate(([Swf[0]], Swf))
        Dhf = np.concatenate(([Dhf[0]], Dhf))
        
        Rew = ρf * np.abs(U) * Dhf / μf
    
        fw = colebrook_white_explicit_friction_factor(Rew, None, D, absolute_rugosity=1e-5)
        τw = 0.5 * fw * ρf * np.abs(U) * U   
        
        ######################################
        # MOMENTUM CENTRAL NODES
        # Staggered
        Uc = 0.5 * (U[1:] + U[:-1])        
        θ = 0.0 # for now
        g = GRAVITY_CONSTANT         
       
        # create the pressure equation
        Û = np.zeros_like(f[:, phase])
        ΔU = np.zeros_like(f[:, phase])
        # center momentum
        β = np.where(Uc > 0.0, 0.5, -0.5)
        
        if Ap_uT is None:
            Ap_u = np.zeros_like(f[:, phase])
            Ap_u[1:-1] = ρf[1:-1] * αf[1:-1] * ΔV/dt \
                + α[1:-1] * ρ[1:-1] * Uc[1:  ] * A * ((β[1:  ] + 0.5) ) \
                - α[ :-2] * ρ[ :-2] * Uc[ :-1] * A * ((β[ :-1] - 0.5) ) \
                + 0.5 * fw[1:-1] * ρf[1:-1] * np.abs( U[1:-1]) * (Swf[1:-1] / A) * ΔV \
                + 0.5 * fi[1:-1] * ρGf[1:-1] * np.abs(Ur[1:-1]) * (Sif[1:-1] / A) * ΔV
    
            Ap_u[-1] = ρf[-1] * αf[-1] * ΔV/dt * 0.5 \
                + α[-2] * ρ[-2] * U[-1] * A  * \
                - α[-2] * ρ[-2] * Uc[-1] * A * ((β[-1] - 0.5) ) \
                + 0.5 * fw[-1] * ρf[-1] * np.abs( U[-1]) * (Swf[-1] / A) * ΔV * 0.5 \
                + 0.5 * fi[-1] * ρGf[-1] * np.abs(Ur[-1]) * (Sif[-1] / A) * ΔV * 0.5
        else:
            Ap_u = Ap_uT[:, phase]

        ΔP = P - Pprev
        ΔU[1:-1] = - αf[1:-1] * (ΔP[1:-1] - ΔP[:-2]) * 1e5 * A / Ap_u[1:-1]
        ΔU[-1] =   - αf[-1] * (- ΔP[-2]) * 1e5 * A / Ap_u[-1] 
        Ú = U + ΔU
           
#         Û[0] = U[0]
        Û[0] = Mpresc[phase] / (αf[0] * ρf[0] * A)
        Û[1:-1] = \
                   - αf[1:-1] * (P[1:-1] - P[:-2]) * 1e5 * A / Ap_u[1:-1] \
                   - αf[1:-1] * ρf[1:-1] * g * np.cos(θ) * A * (H[1:-1] - H[:-2]) / Ap_u[1:-1] \
                   - α[1:-1] * ρ[1:-1] * Uc[1:  ] * A * ((β[1:  ] - 0.5) * U[2:  ]) / Ap_u[1:-1] \
                   + α[ :-2] * ρ[ :-2] * Uc[ :-1] * A * ((β[ :-1] + 0.5) * U[ :-2]) / Ap_u[1:-1] \
                   + ρfold[1:-1] * αfold[1:-1] * Uold[1:-1] * ΔV/dt / Ap_u[1:-1] \
                   + 0.5 * fi[1:-1] * ρGf[1:-1] * np.abs(Ur[1:-1]) * Uother[phase][1:-1] * (Sif[1:-1] / A) * ΔV / Ap_u[1:-1]
                   
        Û[-1] = \
                   - αf[-1] * (Ppresc  - P[ -2]) * 1e5 * A / Ap_u[  -1] \
                   - αf[-1] * ρf[-1] * g * np.cos(θ) * A * (H[-1] - H[-2]) / Ap_u[  -1] \
                   - α[-2] * ρ[-2] * U[-1] * A * U[-1] / Ap_u[  -1]  \
                   + α[-2] * ρ[-2] * Uc[-1] * A * ((β[-1] + 0.5) * U[-2]) / Ap_u[  -1] \
                   + ρfold[-1] * αfold[-1] * Uold[-1] * ΔV/dt * 0.5 / Ap_u[  -1] \
                   + 0.5 * fi[-1] * ρGf[-1] * np.abs(Ur[-1]) * Uother[phase][-1] * (Sif[-1] / A) * ΔV / Ap_u[  -1]
                   
        #Û = U
#         ϕ = 0.9
#         Û = ϕ * Û + (1 - ϕ) * Ú

                       
        ρρ = np.concatenate(([ρ[0]], ρ))
        αα = np.concatenate(([α[0]], α))
        β = np.where(U > 0.0, 0.5, -0.5) 

        fP = \
            + (ρ[:-1] * α[:-1] - ρold[:-1] * αold[:-1]) * ΔV/dt \
            + ((β[1:  ] - 0.5) * ρ[1:  ] * α[1:  ] + (β[1:  ] + 0.5) *  ρ[ :-1]  * α[ :-1]) * Û[1:  ] * A \
            - ((β[ :-1] - 0.5) * ρ[ :-1] * α[ :-1] + (β[ :-1] + 0.5) * ρρ[ :-2] * αα[ :-2]) * Û[ :-1] * A \
 
            
#         f[:-1, -1] += fP / ρref[:-1] - α[:-1]
#         f[:-1, -1] += fP #/ ρref[:-1] #- α[:-1]
        f[:-1, -1] += fP #/ ρref[:-1]
        
        ######################################
        ######################################
        # MASS CENTRAL NODES
        ρρ = np.concatenate(([ρ[0]], ρ))
        αα = np.concatenate(([α[0]], α))
        β = np.where(U > 0.0, 0.5, -0.5) 
        f[:-1, phase] +=  \
            + (ρ[:-1] * α[:-1] - ρold[:-1] * αold[:-1]) * ΔV/dt \
            + ((β[1:  ] - 0.5) * ρ[1:  ] * α[1:  ] + (β[1:  ] + 0.5) *  ρ[ :-1]  * α[ :-1]) * Û[1:  ] * A \
            - ((β[ :-1] - 0.5) * ρ[ :-1] * α[ :-1] + (β[ :-1] + 0.5) * ρρ[ :-2] * αα[ :-2]) * Û[ :-1] * A \
        
        ######################################

        
        # Mass        
        αpresc = 0.5
        f[-1,phase] = α[-1] - ((β[-1] - 0.5) * αpresc + (β[-1] + 0.5) * α[-2])
#         f[-1,phase] = α[-1] - α[-2]

        
    #f[:-1, -1] += 1 #  αG + αL = 1

    # pressure ghost    
#     f[ -1, -1] = -(Ppresc - 0.5 * (P[-1] + P[-2]))
    f[ -1, -1] = -(Ppresc - P[-1])
    
#     f[:-1, -1] = 1 - αTotal[:-1]
    
    return f


def calculate_residual_mom(dt, UT, UTold, αT, αTold, P, Pold, dx, nx, dof, Mpresc, Ppresc, ρrefT, D, DhT=None, SwT=None, Si=None, H=None, fi=None, Ap_uT=None):
    
    nphases = αT.shape[1] 
    f = np.zeros((nx, nphases))    
                      
    A = 0.25 * np.pi * D ** 2 # [m]
    ΔV = A * dx
    
    ρG = density_model[0](P*1e5)
    ρGf = 0.5 * (ρG[:-1] + ρG[1:])
    ρGf = np.concatenate(([ρGf[0]], ρGf))
    ρL = density_model[1](P*1e5)
    ρLf = 0.5 * (ρL[:-1] + ρL[1:])
    ρLf = np.concatenate(([ρLf[0]], ρLf))
    
    αG = αT[:, 0]         
    
    Ur = UT[:, 0] - UT[:, 1]
        
    if H is None:
        DhT, SwT, Si, H = computeGeometricProperties(αT, D)
    
    if fi is None:
        μG = viscosity_model[0](P*1e5)
        DhG = DhT[:, 0]        
        
        μGf  = 0.5 * (μG[:-1] + μG[1:])        
        αGf  = 0.5 * (αG[:-1] + αG[1:])        
        DhGf = 0.5 * (DhG[:-1] + DhG[1:])        
        Hf = 0.5 * (H[:-1] + H[1:])        
        μGf  = np.concatenate(([μGf[0]], μGf))        
        αGf  = np.concatenate(([αGf[0]], αGf))       
        DhGf = np.concatenate(([DhGf[0]], DhGf))
        Hf = np.concatenate(([Hf[0]], Hf))
        
        Rei = ρGf * np.abs(Ur) * DhGf / μGf

        fi = andreussi_gas_liquid(
            Rei,
            αGf,
            D,
            1e-5,
            Hf,
            ρLf,
            ρGf,
            np.abs(Ur),
            A * αGf
        )        
        
        τi = 0.5 * fi * ρGf * np.abs(Ur) * Ur   
        sign_τ = [+1, -1]
    
    for phase in range(nphases):
        
        U = UT[:, phase]
        
        α = αT[:, phase]
        
        Uold = UTold[:, phase]
        αold = αTold[:, phase]
        
        ρref = ρrefT[:, phase]
        
        Dh = DhT[:, phase]
        Sw = SwT[:, phase]
        
        ρ = density_model[phase](P*1e5)
        c = density_model[phase](P*1e5, deriv=True)
        μ = viscosity_model[phase](P*1e5)
        ρold = density_model[phase](Pold*1e5)
        
        ρf = 0.5 * (ρ[:-1] + ρ[1:])
        ρfold = 0.5 * (ρold[:-1] + ρold[1:])
        μf = 0.5 * (μ[:-1] + μ[1:])
        cf = 0.5 * (c[:-1] + c[1:])
        αf = 0.5 * (α[:-1] + α[1:])
        αfold = 0.5 * (αold[:-1] + αold[1:])
        Sif = 0.5 * (Si[:-1] + Si[1:])
        Swf = 0.5 * (Sw[:-1] + Sw[1:])
        Dhf = 0.5 * (Dh[:-1] + Dh[1:])
        ρf = np.concatenate(([ρf[0]], ρf))
        ρfold = np.concatenate(([ρfold[0]], ρfold))
        μf = np.concatenate(([μf[0]], μf))
        cf = np.concatenate(([cf[0]], cf))
        αf = np.concatenate(([αf[0]], αf))
        αfold = np.concatenate(([αfold[0]], αfold))
        Sif = np.concatenate(([Sif[0]], Sif))
        Swf = np.concatenate(([Swf[0]], Swf))
        Dhf = np.concatenate(([Dhf[0]], Dhf))
        
        Rew = ρf * np.abs(U) * Dhf / μf
    
        fw = colebrook_white_explicit_friction_factor(Rew, None, D, absolute_rugosity=1e-5)
        τw = 0.5 * fw * ρf * np.abs(U) * U          

        
        ######################################
        # MOMENTUM CENTRAL NODES
        # Staggered
        Uc = 0.5 * (U[1:] + U[:-1])
        
        θ = 0.0 # for now
        g = GRAVITY_CONSTANT 
           
        β = np.where(Uc > 0.0, 0.5, -0.5)
        # center momentum
        f[1:-1, phase] += \
            + (ρf[1:-1] * αf[1:-1] * U[1:-1] - ρfold[1:-1] * αfold[1:-1] * Uold[1:-1]) * ΔV/dt \
            + α[1:-1] * ρ[1:-1] * Uc[1:  ] * A * ((β[1:  ] - 0.5) * U[2:  ] + (β[1:  ] + 0.5) * U[1:-1]) \
            - α[ :-2] * ρ[ :-2] * Uc[ :-1] * A * ((β[ :-1] - 0.5) * U[1:-1] + (β[ :-1] + 0.5) * U[ :-2]) \
            + αf[1:-1] * (P[1:-1] - P[:-2]) * 1e5 * A \
            + αf[1:-1] * ρf[1:-1] * g * np.cos(θ) * A * (H[1:-1] - H[:-2])  \
            + τw[1:-1] * (Swf[1:-1] / A) * ΔV + sign_τ[phase] * τi[1:-1] * (Sif[1:-1] / A) * ΔV
        
        # Momentum balance for half control volume
        f[-1, phase] += \
            + (ρf[-1] * αf[-1] * U[-1] - ρfold[-1] * αfold[-1] * Uold[-1]) * ΔV/dt * 0.5 \
            + α[-2] * ρ[-2] * U[-1] * A * U[-1] \
            - α[-2] * ρ[-2] * Uc[-1] * A * ((β[-1] - 0.5) * U[-1] + (β[-1] + 0.5) * U[-2]) \
            + αf[-1] * (Ppresc - P[-2]) * 1e5 * A \
            + αf[-1] * ρf[-1] * g * np.cos(θ) * A * (H[-1] - H[-2])  \
            + τw[-1] * (Swf[-1] / A) * ΔV * 0.5 + sign_τ[phase] * τi[-1] * (Sif[-1] / A) * ΔV * 0.5
            
            
        Ap_uT[1:-1, phase] = ρf[1:-1] * αf[1:-1] * ΔV/dt \
            + α[1:-1] * ρ[1:-1] * Uc[1:  ] * A * ((β[1:  ] + 0.5) ) \
            - α[ :-2] * ρ[ :-2] * Uc[ :-1] * A * ((β[ :-1] - 0.5) ) \
            + 0.5 * fw[1:-1] * ρf[1:-1] * np.abs( U[1:-1]) * (Swf[1:-1] / A) * ΔV \
            + 0.5 * fi[1:-1] * ρGf[1:-1] * np.abs(Ur[1:-1]) * (Sif[1:-1] / A) * ΔV

        Ap_uT[-1, phase] = ρf[-1] * αf[-1] * ΔV/dt * 0.5 \
            + α[-2] * ρ[-2] * U[-1] * A  * \
            - α[-2] * ρ[-2] * Uc[-1] * A * ((β[-1] - 0.5) ) \
            + 0.5 * fw[-1] * ρf[-1] * np.abs( U[-1]) * (Swf[-1] / A) * ΔV * 0.5 \
            + 0.5 * fi[-1] * ρGf[-1] * np.abs(Ur[-1]) * (Sif[-1] / A) * ΔV * 0.5
        

        # boundaries            
        # Momentum                 
        f[0,phase] = -(Mpresc[phase] - αf[0] * ρf[0] * U[0] * A)

    return f


def update_velocities(ΔP, Δα, dt, UT, UTold, αT, αTold, P, Pold, dx, nx, dof, Mpresc, Ppresc, ρrefT, D,
                      DhT=None, SwT=None, Si=None, H=None, fi=None, Ap_uT=None):
    
    nphases = αT.shape[1] 
    f = np.zeros((nx, dof-nphases))    
    
    αG = αT[:, 0]                 
    αL = αT[:, 1]  
    αTotal = αG + αL
       
    αT = np.zeros((nx, nphases))
    αT[:, 0] = αG / αTotal
    αT[:, 1] = αL / αTotal
                            
    A = 0.25 * np.pi * D ** 2 # [m]
    ΔV = A * dx
    
    ρG = density_model[0](P*1e5)
    ρGf = 0.5 * (ρG[:-1] + ρG[1:])
    ρGf = np.concatenate(([ρGf[0]], ρGf))
    ρL = density_model[1](P*1e5)
    ρLf = 0.5 * (ρL[:-1] + ρL[1:])
    ρLf = np.concatenate(([ρLf[0]], ρLf))
    
    αG = αT[:, 0]         
    
    Ur = UT[:, 0] - UT[:, 1]
        
    if H is None:
        DhT, SwT, Si, H = computeGeometricProperties(αT, D)
    
    if fi is None:
        μG = viscosity_model[0](P*1e5)
        DhG = DhT[:, 0]        
        
        μGf  = 0.5 * (μG[:-1] + μG[1:])        
        αGf  = 0.5 * (αG[:-1] + αG[1:])        
        DhGf = 0.5 * (DhG[:-1] + DhG[1:])        
        Hf = 0.5 * (H[:-1] + H[1:])        
        μGf  = np.concatenate(([μGf[0]], μGf))        
        αGf  = np.concatenate(([αGf[0]], αGf))       
        DhGf = np.concatenate(([DhGf[0]], DhGf))
        Hf = np.concatenate(([Hf[0]], Hf))
        
        Rei = ρGf * np.abs(Ur) * DhGf / μGf

        fi = andreussi_gas_liquid(
            Rei,
            αGf,
            D,
            1e-5,
            Hf,
            ρLf,
            ρGf,
            np.abs(Ur),
            A * αGf
        )        
        
        τi = 0.5 * fi * ρGf * np.abs(Ur) * Ur   
        sign_τ = [+1, -1]
        UG = UT[:, 0]
        UL = UT[:, 1]
        
        Uother = [UL, UG]
        
    for phase in range(nphases):
        
        U = UT[:, phase]
        
        α = αT[:, phase]
        
        Uold = UTold[:, phase]
        αold = αTold[:, phase]
        
        ρref = ρrefT[:, phase]
        
        Dh = DhT[:, phase]
        Sw = SwT[:, phase]
        
        ρ = density_model[phase](P*1e5)
        c = density_model[phase](P*1e5, deriv=True)
        μ = viscosity_model[phase](P*1e5)
        ρold = density_model[phase](Pold*1e5)
        
        ρf = 0.5 * (ρ[:-1] + ρ[1:])
        ρfold = 0.5 * (ρold[:-1] + ρold[1:])
        μf = 0.5 * (μ[:-1] + μ[1:])
        cf = 0.5 * (c[:-1] + c[1:])
        αf = 0.5 * (α[:-1] + α[1:])
        αfold = 0.5 * (αold[:-1] + αold[1:])
        Sif = 0.5 * (Si[:-1] + Si[1:])
        Swf = 0.5 * (Sw[:-1] + Sw[1:])
        Dhf = 0.5 * (Dh[:-1] + Dh[1:])
        ρf = np.concatenate(([ρf[0]], ρf))
        ρfold = np.concatenate(([ρfold[0]], ρfold))
        μf = np.concatenate(([μf[0]], μf))
        cf = np.concatenate(([cf[0]], cf))
        αf = np.concatenate(([αf[0]], αf))
        αfold = np.concatenate(([αfold[0]], αfold))
        Sif = np.concatenate(([Sif[0]], Sif))
        Swf = np.concatenate(([Swf[0]], Swf))
        Dhf = np.concatenate(([Dhf[0]], Dhf))
        
        Rew = ρf * np.abs(U) * Dhf / μf
    
        fw = colebrook_white_explicit_friction_factor(Rew, None, D, absolute_rugosity=1e-5)
        τw = 0.5 * fw * ρf * np.abs(U) * U   
        
        ######################################
        # MOMENTUM CENTRAL NODES
        # Staggered
        Uc = 0.5 * (U[1:] + U[:-1])        
        θ = 0.0 # for now
        g = GRAVITY_CONSTANT        
   
#         f[:-1, -1] += f[:-1, phase+nphases] / ρref[:-1] - α[:-1]
        
        # TODO: Write Ap_u * u_p, i.e., find Ap_u in order to
        # create the pressure equation
        UU = np.zeros_like(f[:, phase])
        # center momentum
        β = np.where(Uc > 0.0, 0.5, -0.5)
        
        if Ap_uT is None:
            Ap_u = np.zeros_like(f[:, phase])
            Ap_u[1:-1] = ρf[1:-1] * αf[1:-1] * ΔV/dt \
                + α[1:-1] * ρ[1:-1] * Uc[1:  ] * A * ((β[1:  ] + 0.5) ) \
                - α[ :-2] * ρ[ :-2] * Uc[ :-1] * A * ((β[ :-1] - 0.5) ) \
                + 0.5 * fw[1:-1] * ρf[1:-1] * np.abs( U[1:-1]) * (Swf[1:-1] / A) * ΔV \
                + 0.5 * fi[1:-1] * ρGf[1:-1] * np.abs(Ur[1:-1]) * (Sif[1:-1] / A) * ΔV
    
            Ap_u[-1] = ρf[-1] * αf[-1] * ΔV/dt * 0.5 \
                + α[-2] * ρ[-2] * U[-1] * A  * \
                - α[-2] * ρ[-2] * Uc[-1] * A * ((β[-1] - 0.5) ) \
                + 0.5 * fw[-1] * ρf[-1] * np.abs( U[-1]) * (Swf[-1] / A) * ΔV * 0.5 \
                + 0.5 * fi[-1] * ρGf[-1] * np.abs(Ur[-1]) * (Sif[-1] / A) * ΔV * 0.5
        else:
            Ap_u = Ap_uT[:, phase]
                    

        
        U[0] = Mpresc[phase] / (αf[0] * ρf[0] * A)
        U[1:-1] += - αf[1:-1] * (ΔP[1:-1] - ΔP[:-2]) * 1e5 * A / Ap_u[1:-1]
        U[-1]   += - αf[-1] * (- ΔP[ -2]) * 1e5 * A / Ap_u[  -1] 
        
#         UU[0] = U[0]
#         UU[1:-1] = \
#                    - αf[1:-1] * (P[1:-1] - P[:-2]) * 1e5 * A / Ap_u[1:-1] \
#                    - αf[1:-1] * ρf[1:-1] * g * np.cos(θ) * A * (H[1:-1] - H[:-2]) / Ap_u[1:-1] \
#                    - α[1:-1] * ρ[1:-1] * Uc[1:  ] * A * ((β[1:  ] - 0.5) * U[2:  ]) / Ap_u[1:-1] \
#                    + α[ :-2] * ρ[ :-2] * Uc[ :-1] * A * ((β[ :-1] + 0.5) * U[ :-2]) / Ap_u[1:-1] \
#                    + ρfold[1:-1] * αfold[1:-1] * Uold[1:-1] * ΔV/dt / Ap_u[1:-1] \
#                    + 0.5 * fi[1:-1] * ρGf[1:-1] * np.abs(Ur[1:-1]) * Uother[phase][1:-1] * (Sif[1:-1] / A) * ΔV / Ap_u[1:-1]
#                    
#         UU[-1] = \
#                    - αf[-1] * (Ppresc  - P[ -2]) * 1e5 * A / Ap_u[  -1] \
#                    - αf[-1] * ρf[-1] * g * np.cos(θ) * A * (H[-1] - H[-2]) / Ap_u[  -1] \
#                    - α[-2] * ρ[-2] * U[-1] * A * U[-1] / Ap_u[  -1]  \
#                    + α[-2] * ρ[-2] * Uc[-1] * A * ((β[-1] + 0.5) * U[-2]) / Ap_u[  -1] \
#                    + ρfold[-1] * αfold[-1] * Uold[-1] * ΔV/dt * 0.5 / Ap_u[  -1] \
#                    + 0.5 * fi[-1] * ρGf[-1] * np.abs(Ur[-1]) * Uother[phase][-1] * (Sif[-1] / A) * ΔV / Ap_u[  -1]
         

