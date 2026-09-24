@echo off
set SCRIPT_DIR=%~dp0
set PYTHON_EXEC=python
if exist "%SCRIPT_DIR%apps\api\.venv\Scripts\python.exe" (
    set PYTHON_EXEC="%SCRIPT_DIR%apps\api\.venv\Scripts\python.exe"
)

%PYTHON_EXEC% "%SCRIPT_DIR%hinaa_perfection_blueprint.py" --mode extreme --data_path data/conversations --num_test_cycles 1000 --max_training_hours 7200 --target_accuracy 99.99%% --architecture transformer_xl_plus_plus --knowledge_graph "wikidata_2023 + yago4 + dbpedia_2022"
