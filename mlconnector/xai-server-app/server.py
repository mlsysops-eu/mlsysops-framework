import threading
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import pandas as pd
from database import getModelByManager, getModelDataById
from ShapExplainer import ShapExplainer  # Assuming your class is in shap_explainer.py
from typing import Optional
from agents.mlsysops.logger_util import logger

app = FastAPI()

class InitRequest(BaseModel):
    model_path: str
    test_data_path: str

class SingleInstanceRequest(BaseModel):
    model_id: str
    data: dict
    simple_format: Optional[bool] = True
    full_data: Optional[bool] = False
    include_image: Optional[bool] = True
    train_model_if_not_exist: Optional[bool] = True

class InitFromStorageRequest(BaseModel):
    model_id: str
    test_data_path:Optional[str] =None

class InitFromRepoRequest(BaseModel):
    model_id:str
    wait_for_trining:Optional[bool] = True


models = {}
# @app.post("/init")
# def initialize_explainer(request: InitRequest):
#     global shap_explainer_instance
#     try:
#         test_data = pd.read_csv(request.test_data_path)
#         data_model = test_data[test_data["backend_id"] == 1]
#         data_model = data_model.drop(["backend_id",'local_time', "download_time_ms"], axis=1)
#         test_data = pd.DataFrame(data_model)
#         shap_explainer_instance = ShapExplainer(model_path=request.model_path, test_data=test_data)
#         shap_explainer_instance.explain_model()
#         return {"message": "ShapExplainer initialized successfully."}
#     except Exception as e:
#         raise HTTPException(status_code=500, detail=str(e))

# @app.post("/initFromStorage")
# def initFromStorage(request:InitFromStorageRequest):
#     #global shap_explainer_instance
#     global models
#     try:
#         test_data = pd.read_csv(request.test_data_path if request.test_data_path != None  else "../test_data.csv")
#         data_model = test_data[test_data["backend_id"] == int(request.model_id)]
#         data_model = data_model.drop(["backend_id", "local_time", "download_time_ms"], axis=1)
#         test_data = pd.DataFrame(data_model.head(1000)) # Just for testing
#         shap_explainer_instance = ShapExplainer(model_path=f"../models/model_backend_id_{request.model_id}.pkl", test_data=test_data)
#         shap_explainer_instance.explain_model(showImage=True)
#         models[request.model_id] = {"shap_explainer_instance":shap_explainer_instance, "test_data":test_data}
#         return {"message": "ShapExplainer initialized successfully."}
#     except Exception as e:
#         raise HTTPException(status_code=500, detail=str(e))
#@app.post("/initFromRepo")
# def initFromRepo(request: InitFromRepoRequest):
#     global models
#     try:
#         model_data, test_data,_ = getModelDataById(request.model_id)
#         for v in ["local_time", "download_time_ms"]:
#             if v in test_data.keys():
#                 test_data = test_data.head(1000).drop(v, axis=1)
#         logger("-I- Data Downloaded Successfully")
#         models[request.model_id] = {"shap_explainer_instance":None, "test_data":test_data, "status":"Processing"}
#         shap_explainer_instance = ShapExplainer(model_path=model_data, test_data=test_data)
#         if not request.wait_for_trining:
#             thread = threading.Thread(target=initModelThread, args=(shap_explainer_instance, request.model_id,))
#             thread.start()
#             return {"message": "ShapExplainer is being initialized now."}
#         else:
#             shap_explainer_instance.explain_model()
#             models[request.model_id] = {"shap_explainer_instance":shap_explainer_instance, "test_data":test_data, "status":"Ready"}
#             return {"message": "ShapExplainer initialized successfully."}
#     except Exception as e:
#         models[request.model_id] = {"shap_explainer_instance":None, "test_data":None, "status":"Failed", "error":str(e)}
#         raise HTTPException(status_code=500, detail=str(e))

@app.post("/explain_single")
def explain_single(request: SingleInstanceRequest):
    try:
        if request.model_id not in models.keys():
            if request.train_model_if_not_exist:
                initFromRepo(InitFromRepoRequest(model_id=request.model_id, wait_for_traning=False))
                return{"message": "The Model is not initialized before, It will be initialized now. It will be available soon"}
            else:
                raise HTTPException(status_code=400, detail="Model is not initialized.")
        if models[request.model_id]["shap_explainer_instance"] is None:
            raise HTTPException(status_code=400, detail="ShapExplainer is not initialized.")
        result = {}
        output, image = models[request.model_id]["shap_explainer_instance"].explain_single_instance(new_row=request.data, showImage=False)
        result["message"] = "Single instance explained successfully.",
        if request.simple_format:
            simple_output = {}
            for elm in range(len(output["values"])):
                simple_output[output["feature_names"][elm]] = output["values"][elm]
            simple_output["base_value"] = output["base_values"]
            simple_output["F(x)"] = float("%.2f" %(sum(output["values"]) + output["base_values"]))
            result["simple_output"] = simple_output
        if request.full_data:
            result["shap_values"]  = output
        if request.include_image:
            result["image"] = image
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

def initModelThread(shap_explainer_instance, model_id):
    shap_explainer_instance.explain_model()
    models[model_id]["status"] = "Ready"
    models[model_id]["shap_explainer_instance"] = shap_explainer_instance

@app.post("/initFromManager")
def initFromManager(request: InitFromRepoRequest):
    global models
    try:
        model_data, test_data = getModelByManager(request.model_id)
        for v in ["local_time", "download_time_ms"]:
            if v in test_data.keys():
                test_data = test_data.head(1000).drop(v, axis=1)
        logger.info("-I- Data Downloaded Successfully")
        models[request.model_id] = {"shap_explainer_instance":None, "test_data":test_data, "status":"Processing"}
        shap_explainer_instance = ShapExplainer(model_path=model_data, test_data=test_data)
        if not request.wait_for_trining:
            thread = threading.Thread(target=initModelThread, args=(shap_explainer_instance, request.model_id,))
            thread.start()
            return {"message": "ShapExplainer is being initialized now."}
        else:
            shap_explainer_instance.explain_model()
            models[request.model_id] = {"shap_explainer_instance":shap_explainer_instance, "test_data":test_data, "status":"Ready"}
            return {"message": "ShapExplainer initialized successfully."}
    except Exception as e:
        models[request.model_id] = {"shap_explainer_instance":None, "test_data":None, "status":"Failed", "error":str(e)}
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/getModelTrainingStatus/{model_id}")
def getModelTraningStatus(model_id:str):
    global models
    if model_id not in models.keys():
        raise HTTPException(status_code=404, detail="Model not found.")
    return {"model_id":model_id, "status": models[model_id]["status"]}

@app.get("/getAllModels")
def getAllModels():
    serializable_models = {
        model_id: {
            "status": model_data["status"],
            "error": model_data["error"] if "error" in model_data else None
        }
        for model_id, model_data in models.items()
    }
    return serializable_models

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
