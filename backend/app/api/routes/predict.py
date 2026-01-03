# backend/app/api/routes/predict.py
from fastapi import APIRouter
from pydantic import BaseModel
import joblib
from app.utils.preprocessing import preprocess_input

router = APIRouter()

# Load the model once when the app starts
MODEL_PATH = "app/models/food_symptom_model.pkl"
model = joblib.load(MODEL_PATH)

# Define the expected input schema
class UserInput(BaseModel):
    feature1: float
    feature2: int
    feature3: str
    # add all relevant features your model expects

@router.post("/predict")
def predict(input_data: UserInput):
    df = preprocess_input(input_data.dict())
    prediction = model.predict(df)[0]
    probability = model.predict_proba(df)[0].tolist()  # optional probability
    return {"prediction": int(prediction), "probability": probability}

