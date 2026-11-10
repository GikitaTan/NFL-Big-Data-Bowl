"""Score feature rows without requiring outcomes. Use train.feature_row to build rows."""
import argparse
import joblib
import pandas as pd

def predict_expected_yards(feature_rows, model_path='results/tracking_model.joblib'):
    model=joblib.load(model_path)
    missing=set(model['features'])-set(feature_rows.columns)
    if missing:
        raise ValueError('Missing feature columns: '+str(sorted(missing)))
    return model['pipeline'].predict(feature_rows[model['features']])

if __name__=='__main__':
    p=argparse.ArgumentParser()
    p.add_argument('--features',required=True)
    p.add_argument('--model',default='results/tracking_model.joblib')
    p.add_argument('--out',default='predictions.csv')
    a=p.parse_args(); rows=pd.read_csv(a.features)
    out=rows[[c for c in ['gameId','playId','week'] if c in rows]].copy()
    out['expected_net_yards']=predict_expected_yards(rows,a.model)
    out.to_csv(a.out,index=False)
    print(out.head().to_string(index=False))
