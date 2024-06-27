@echo off
docker-compose down
cd ..\..\..\backend
docker build -t api .
cd ..\deployment\production
docker-compose up -d
pause