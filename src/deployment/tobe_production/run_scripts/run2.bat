@echo off
docker-compose down
cd ..\..\..\backend
docker build -t api .
cd ..\deployment\production\tobe_production
docker-compose up -d
pause
