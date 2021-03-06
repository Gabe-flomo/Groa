# This is the file that implements a flask server to do inferences. It's the file that you will modify to
# implement the scoring for your own algorithm.

from __future__ import print_function

import os
import json
import gensim
import numpy as np
import pandas as pd
import pickle
import StringIO
import sys
import signal
import traceback
import glob

import flask

import pandas as pd

prefix = '/opt/ml/'
model_path = os.path.join(prefix, 'model')

# A singleton for holding the model. This simply loads the model and holds it.
# It has a predict function that does a prediction based on the model and the input data.

class ScoringService(object):
    model = None                # Where we keep the model when it's loaded

    @classmethod
    def get_model(cls):
        """Get the model object for this instance, loading it if it's not already loaded."""
        if cls.model == None:
            # load the gensim model
            with open(os.path.join(model_path, 'word2vec_2.model'), 'r') as inp:
                gensim.models.Word2Vec.load(inp)
            w2v_model = gensim.models.Word2Vec.load("word2vec_2.model")
            # keep only the normalized vectors.
            # This saves memory but makes the model untrainable (read-only).
            w2v_model = w2v_model.init_sims(replace=True)
            cls.model = w2v_model
        return cls.model

    @classmethod
    def predict(cls, input):
        """For the input, do the predictions and return them.

        Args:
            input (a pandas dataframe): The data on which to do the predictions. There will be
                one prediction per row in the dataframe"""
        # get the model
        clf = cls.get_model()

        # convert csv
        input = pd.read_csv(input)

        def _aggregate_vectors(movies):
            # get the vector average of the movies in the input
            movie_vec = []
            for i in movies:
                try:
                    movie_vec.append(clf[i])
                except KeyError:
                    continue

            return np.mean(movie_vec, axis=0)

        def _similar_movies(v, n = 6):
            # extract most similar movies for the input vector
            return clf.similar_by_vector(v, topn= n+1)[1:]

        new_input = [[x[0].lstrip("0")] for x in input[input.columns[0]]] # remove leading zeroes
        recs = _similar_movies(_aggregate_vectors(new_input))
        return recs

# The flask app for serving predictions
app = flask.Flask(__name__)

@app.route('/ping', methods=['GET'])
def ping():
    """Determine if the container is working and healthy. In this sample container, we declare
    it healthy if we can load the model successfully."""

    status = 200
    folders = [f for f in glob.glob(model_path+'/*')]

    for f in folders:
        print(f)
    return flask.Response(response='\n', status=status, mimetype='application/csv')

@app.route('/invocations', methods=['POST'])
def transformation():
    """Do an inference on a single batch of data. In this sample server, we take data as CSV, convert
    it to a pandas data frame for internal use and then convert the predictions back to CSV (which really
    just means one prediction per line, since there's a single column.
    """
    data = None

    # Convert from CSV to pandas
    if flask.request.content_type == 'text/csv':
        data = flask.request.data.decode('utf-8')
        s = StringIO.StringIO(data)
        data = pd.read_csv(s, header=None)
    else:
        return flask.Response(response='This predictor only supports CSV data', status=415, mimetype='text/plain')

    print('Invoked with {} records'.format(data.shape[0]))

    # Do the prediction
    predictions = ScoringService.predict(data)

    # Convert from numpy back to CSV
    out = StringIO.StringIO()
    pd.DataFrame({'results':predictions}).to_csv(out, header=False, index=False)
    result = out.getvalue()

    return flask.Response(response=result, status=200, mimetype='text/csv')
