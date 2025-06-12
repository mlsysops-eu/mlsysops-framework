# !/usr/bin/python3
# Author John Byabazaire


from sqlalchemy.orm import Session
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from models.mlresources import MLResources
from schema.mlresource import MLResourceCreate


async def get_feature_by_id(db: AsyncSession, resource_id: str):
    query = select(MLResources).where(MLResources.resource_id == resource_id)
    result = await db.execute(query)
    return result.scalar_one_or_none()


async def get_feature_by_model_id(db: AsyncSession, model_id: str):
    query = select(MLResources).where(MLResources.modelid == model_id)
    result = await db.execute(query)
    return result.scalars().all()


async def return_all_model_features(db: AsyncSession, skip: int = 0, limit: int = 100):
    query = select(MLResources).offset(skip).limit(limit)
    result = await db.execute(query)
    return result.scalar_one_or_none()


async def create_fetaure(db: AsyncSession, mlresource: MLResourceCreate):
    new_feature = MLResources(
        resource_id = mlresource.resource_id,
        explanation_flag = mlresource.explanation_flag,
        modelrecall = mlresource.modelrecall,
        modelprecision = mlresource.modelprecision,
        modelaccuracy = mlresource.modelaccuracy,
        min_core = mlresource.min_core,
        min_ram = mlresource.min_ram,
        min_disk = mlresource.min_disk,
        input_type = mlresource.input_type,
        out_type = mlresource.out_type,
        modelid = mlresource.modelid,
    )
    #async with db.begin():
    db.add(new_feature)
    await db.commit()
    await db.refresh(new_feature)
    return new_feature


async def update_feature(
        db: AsyncSession, 
        resource_id: str,
        feature: MLResourceCreate 
    ):
    existing_feature = await get_feature_by_id(db=db, resource_id=resource_id)
    for field, value in feature.model_dump(exclude_unset=True).items():
        setattr(existing_feature, field, value)
    #async with db.begin():
    await db.commit()
    await db.refresh(existing_feature)
    return existing_feature