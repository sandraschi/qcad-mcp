# Per-repo fleet start config for qcad-mcp
# Edit ports/backend target here - start.ps1 is fleet-standard.
@{
    Name         = 'qcad-mcp'
    BackendPort  = 11966
    FrontendPort = 11967
    HealthPath   = '/api/v1/status'
    WebRoot      = 'D:\Dev\repos\qcad-mcp\webapp'
    Backend = @{
        Kind          = 'uvicorn'
        UvicornTarget = 'qcad_mcp.server:app'
        SyncExtras    = @('dev')
        Env           = @{ WEB_PORT = '11966' }
    }
    Frontend = @{
        Kind           = 'vite-npm'
        PackageManager = 'npm'
        PortEnvVar     = 'VITE_PORT'
        ApiTargetEnv   = 'VITE_API_TARGET'
    }
}

