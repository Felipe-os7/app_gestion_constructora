pipeline {
    agent any

    options {
        timestamps()
        timeout(time: 30, unit: 'MINUTES')
        disableConcurrentBuilds()
    }

    environment {
        DJANGO_SETTINGS_MODULE = 'app_gestion.settings'
        DJANGO_DEBUG = 'False'
        DJANGO_SECRET_KEY = 'ci-only-secret'
        DB_NAME = 'constructora'
        DB_USER = 'app_user'
        DB_HOST = '127.0.0.1'
        DB_PORT = '3306'
        MYSQL_CONTAINER = 'jenkins-mysql-ci'
    }

    stages {
        stage('Instalar dependencias') {
            steps {
                powershell '''
                    $python = $null
                    $pythonArgs = @()
                    $launcher = Get-Command py -ErrorAction SilentlyContinue
                    if ($launcher) {
                        & $launcher.Source -3 --version *> $null
                        if ($LASTEXITCODE -eq 0) {
                            $python = $launcher.Source
                            $pythonArgs = @('-3')
                        }
                    }

                    if (-not $python) {
                        $candidates = @(
                            'C:\\Program Files\\Python313\\python.exe',
                            'C:\\Program Files\\Python314\\python.exe',
                            'C:\\Program Files\\Python312\\python.exe'
                        )
                        foreach ($candidate in $candidates) {
                            if (Test-Path $candidate) {
                                $python = $candidate
                                break
                            }
                        }
                    }

                    if (-not $python) {
                        throw 'No se encontró Python en el agente de Jenkins.'
                    }

                    & $python @pythonArgs -m pip install --upgrade pip
                    & $python @pythonArgs -m pip install -r requirements.txt
                    & $python @pythonArgs -m pip install flake8 pytest pytest-django
                    if ($LASTEXITCODE -ne 0) {
                        throw 'No se pudieron instalar las dependencias Python.'
                    }
                '''
            }
        }

        stage('Iniciar MySQL') {
            steps {
                withCredentials([
                    string(credentialsId: 'mysql-root-password', variable: 'MYSQL_ROOT_PASSWORD'),
                    string(credentialsId: 'mysql-app-password', variable: 'DB_PASSWORD')
                ]) {
                    powershell '''
                        docker rm -f $env:MYSQL_CONTAINER 2>$null
                        docker run --name $env:MYSQL_CONTAINER `
                            --env MYSQL_DATABASE=$env:DB_NAME `
                            --env MYSQL_USER=$env:DB_USER `
                            --env MYSQL_PASSWORD=$env:DB_PASSWORD `
                            --env MYSQL_ROOT_PASSWORD=$env:MYSQL_ROOT_PASSWORD `
                            --env MYSQL_ROOT_HOST=% `
                            --publish 3306:3306 `
                            --pull always `
                            --detach mysql:8.4
                        if ($LASTEXITCODE -ne 0) {
                            throw 'No se pudo iniciar MySQL 8.4 en Docker.'
                        }

                        $mysqlVersion = docker exec $env:MYSQL_CONTAINER mysql --version
                        if (-not $mysqlVersion.Contains('8.4')) {
                            docker logs $env:MYSQL_CONTAINER
                            throw "La imagen MySQL usada no es 8.4: $mysqlVersion"
                        }

                        $ready = $false
                        for ($attempt = 1; $attempt -le 60; $attempt++) {
                            docker exec $env:MYSQL_CONTAINER mysqladmin ping `
                                --host=127.0.0.1 --protocol=tcp `
                                --user=root --password=$env:MYSQL_ROOT_PASSWORD --silent
                            if ($LASTEXITCODE -eq 0) {
                                $ready = $true
                                break
                            }
                            Start-Sleep -Seconds 2
                        }

                        if (-not $ready) {
                            docker logs $env:MYSQL_CONTAINER
                            throw 'MySQL no estuvo disponible a tiempo.'
                        }

                        docker exec $env:MYSQL_CONTAINER mysql `
                            --host=127.0.0.1 --protocol=tcp `
                            --user=root --password=$env:MYSQL_ROOT_PASSWORD `
                            --execute="GRANT ALL PRIVILEGES ON *.* TO '$env:DB_USER'@'%'; FLUSH PRIVILEGES;"
                        if ($LASTEXITCODE -ne 0) {
                            throw 'No se pudieron conceder permisos de creaci�n de bases a app_user.'
                        }
                    '''
                }
            }
        }
        stage('Lint') {
            steps {
                powershell '''
                    $python = (Get-Command py -ErrorAction SilentlyContinue).Source
                    if ($python) {
                        & $python -3 -m flake8 . --count --select=E9,F63,F7,F82 --show-source --statistics
                    } else {
                        & 'C:\\Program Files\\Python313\\python.exe' -m flake8 . --count --select=E9,F63,F7,F82 --show-source --statistics
                    }
                    if ($LASTEXITCODE -ne 0) {
                        throw 'Flake8 encontró errores en el proyecto.'
                    }
                '''
            }
        }

        stage('Pruebas') {
            steps {
                withCredentials([
                    string(credentialsId: 'mysql-app-password', variable: 'DB_PASSWORD')
                ]) {
                    powershell '''
                        $python = (Get-Command py -ErrorAction SilentlyContinue).Source
                        $pythonArgs = @()
                        if ($python) {
                            $pythonArgs = @('-3')
                        } else {
                            $python = 'C:\\Program Files\\Python313\\python.exe'
                        }

                        & $python @pythonArgs manage.py migrate --noinput
                        if ($LASTEXITCODE -ne 0) {
                            throw 'Las migraciones de Django fallaron.'
                        }

                        & $python @pythonArgs -m pytest --junitxml=pytest-results.xml
                        if ($LASTEXITCODE -ne 0) {
                            throw 'La suite de pruebas falló.'
                        }
                    '''
                }
            }
        }

        stage('Desplegar producción') {
            when {
                branch 'main'
            }
            steps {
                withCredentials([string(credentialsId: 'render-deploy-hook', variable: 'RENDER_DEPLOY_HOOK_URL')]) {
                    powershell '''
                        if ([string]::IsNullOrWhiteSpace($env:RENDER_DEPLOY_HOOK_URL)) {
                            throw 'Falta la credencial Jenkins render-deploy-hook.'
                        }
                        Invoke-WebRequest -Uri $env:RENDER_DEPLOY_HOOK_URL -Method Post -UseBasicParsing
                    '''
                }
            }
        }
    }

    post {
        always {
            junit testResults: 'pytest-results.xml', allowEmptyResults: true
            powershell '''
                docker rm -f $env:MYSQL_CONTAINER 2>$null
            '''
        }
    }
}
