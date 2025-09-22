import os

# One host for everything
IP = os.getenv("MLS_API_IP", "172.25.27.243")

# Ports: 8000 for general, 8090 for ML
PORT_APP = int(os.getenv("MLS_API_PORT", "8000"))
PORT_ML = int(os.getenv("MLS_ML_API_PORT", "8090"))

# Bases
BASE = f"http://{IP}:{PORT_APP}"  # apps/infra/manage/agent
BASE_APP = BASE  # alias, optional
BASE_ML = f"http://{IP}:{PORT_ML}"  # ml (models, training, deployments, inference)
