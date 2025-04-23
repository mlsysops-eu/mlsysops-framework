from fastapi import APIRouter, HTTPException

router = APIRouter()

# GET all customers
@router.put("/management/set_mode", tags=["Management"])
async def set_management_mode():
    return [{"customer_id": 1, "name": "John Doe"}, {"customer_id": 2, "name": "Jane Doe"}]

# POST a new customer
@router.put("/management/get_app_level_explanaition", tags=["Management"])
async def get_app_level_explanaition():
    return {"message": "Customer created"}

# DELETE a customer by ID
@router.put("/management/{system_target}", tags=["Management"])
async def set_system_target(system_target: int):
    return {"message": "Customer deleted"}
