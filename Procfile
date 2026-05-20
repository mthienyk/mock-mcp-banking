release: python -c "from services import run_deploy_setup; run_deploy_setup()"
web: uvicorn main:app --host 0.0.0.0 --port $PORT
