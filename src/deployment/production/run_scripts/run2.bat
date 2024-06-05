@echo off
docker-compose down
cd ..\..\..\backend
docker build -t api .
cd ..\deployment\light
docker-compose up -d
pause