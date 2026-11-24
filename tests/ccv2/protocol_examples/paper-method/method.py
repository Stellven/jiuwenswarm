"""Three CPU operations using upstream MAPIE, not an interval substitute."""
import json
import pickle
import sys
from pathlib import Path

import numpy as np
from mapie.regression import SplitConformalRegressor
from sklearn.linear_model import LinearRegression


def run(packet):
    inputs = packet['inputs']
    output = Path(packet['output_dir'])
    output.mkdir(parents=True, exist_ok=True)
    capability = packet['capability']
    if capability == 'fit_calibrate':
        data = inputs['data']
        model = SplitConformalRegressor(estimator=LinearRegression(), confidence_level=0.9, prefit=False)
        model.fit(np.asarray(data['train_x']), np.asarray(data['train_y']))
        model.conformalize(np.asarray(data['calibrate_x']), np.asarray(data['calibrate_y']))
        with (output / 'model.pkl').open('wb') as stream:
            pickle.dump(model, stream)
        return {'outcome': 'ok', 'outputs': {'model': {'path': 'model.pkl'}}}
    if capability == 'predict_intervals':
        # Artifacts are accepted only after the host has verified their release-store digest.
        with Path(inputs['model']['path']).open('rb') as stream:
            model = pickle.load(stream)
        point, intervals = model.predict_interval(np.asarray(inputs['data']['x']))
        confidence_levels = [float(1 - alpha) for alpha in model._alphas]
        if len(confidence_levels) != 1:
            raise ValueError('This capsule expects one model confidence level')
        values = {'point': point.tolist(), 'lower': intervals[:, 0, 0].tolist(),
                  'upper': intervals[:, 1, 0].tolist(), 'confidence_level': confidence_levels[0]}
        (output / 'intervals.json').write_text(json.dumps(values), encoding='utf-8')
        return {'outcome': 'ok', 'outputs': {'intervals': {'path': 'intervals.json'}}}
    if capability == 'evaluate':
        values = json.loads(Path(inputs['intervals']['path']).read_text(encoding='utf-8'))
        lower, upper = np.asarray(values['lower']), np.asarray(values['upper'])
        labels = np.asarray(inputs['labels'])
        if labels.ndim != 1 or lower.ndim != 1 or upper.ndim != 1 or not labels.size:
            raise ValueError('labels and interval bounds must be nonempty one-dimensional arrays')
        if labels.shape != lower.shape or upper.shape != lower.shape:
            raise ValueError('labels and interval bounds must have equal shapes')
        if not all(np.all(np.isfinite(values)) for values in (labels, lower, upper)):
            raise ValueError('labels and interval bounds must be finite')
        if np.any(lower > upper):
            raise ValueError('interval lower bounds must not exceed upper bounds')
        return {'outcome': 'ok', 'outputs': {'coverage': float(np.mean((labels >= lower) & (labels <= upper))),
                'mean_width': float(np.mean(upper - lower)), 'count': int(labels.size)}}
    raise ValueError('unknown capability: ' + capability)


if __name__ == '__main__':
    try:
        print(json.dumps(run(json.load(sys.stdin))))
    except Exception as error:
        print(json.dumps({'outcome': 'error', 'outputs': {}, 'error': {'code': 'MAPIE_ERROR', 'message': str(error)}}))
        sys.exit(1)

