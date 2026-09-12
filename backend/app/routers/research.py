from fastapi import APIRouter, HTTPException
from app.db.connection import get_db

router = APIRouter(prefix="/api/research", tags=["Research"])

@router.get("/summary")
def get_research_summary():
    """
    Returns the latest comprehensive research summary from Phase 8.
    """
    try:
        db = get_db()
        # Find the latest document based on created_at
        doc = db["research_analysis"].find_one(sort=[("created_at", -1)])
        if not doc:
            raise HTTPException(status_code=404, detail="No research summary found. Run Phase 8 analysis first.")
        
        # Convert ObjectId to string for JSON serialization
        doc["_id"] = str(doc["_id"])
        
        # Clean nested ObjectIds if any (specifically in forecasting_validation_summary)
        if "forecasting_validation_summary" in doc and doc["forecasting_validation_summary"]:
            if "_id" in doc["forecasting_validation_summary"]:
                doc["forecasting_validation_summary"]["_id"] = str(doc["forecasting_validation_summary"]["_id"])
                
        return {"status": "ok", "data": doc}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch research summary: {str(e)}")

@router.get("/dataset")
def get_forecasting_dataset():
    """
    Returns the weekly forecasting dataset.
    """
    try:
        db = get_db()
        # Return all weeks sorted chronologically
        docs = list(db["forecasting_dataset"].find().sort("week_start_date", 1))
        
        if not docs:
            raise HTTPException(status_code=404, detail="No forecasting dataset found.")
            
        for doc in docs:
            doc["_id"] = str(doc["_id"])
            
        return {"status": "ok", "data": docs}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch forecasting dataset: {str(e)}")

