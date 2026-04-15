@echo off
rem llama-server (llama.cpp) backend translation batch file
rem
rem Usage:
rem   llama-translate.bat -i input_file [-o output_file] [-c]
rem
rem Examples:
rem   llama-translate.bat -i temp\Empyrion_RE2_localization_work.txt
rem   llama-translate.bat -i input.txt -o output.txt -c
rem
rem   %~dp0  = directory path of this batch file
rem   %*     = all arguments passed to this batch file
rem   --backend llama : use llama-server (localhost:8080) instead of Ollama
rem
rem To change llama-server host:
rem   llama-translate.bat -i input.txt --llama-host http://localhost:9090

"%~dp0.venv\Scripts\python.exe" "%~dp0ollama_translate.py" --backend llama %*
