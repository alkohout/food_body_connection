# backend/app/utils/preprocessing.py
import pandas as pd

def preprocess_input(input_dict):
    """
    Convert user input (dict) into the DataFrame format your model expects.
    """
    df = pd.DataFrame([input_dict])
    
    # Example: if you used one-hot encoding or scaling during training
    # df = do_some_transformations(df)
    
    return df

