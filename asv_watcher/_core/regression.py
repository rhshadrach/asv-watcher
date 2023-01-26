class Regression:
    def __init__(self, asv_name, asv_params, data, bad_hash, good_hash, plot_data):
        self._asv_name = asv_name
        self._asv_params = asv_params
        self._data = data
        self._bad_hash = bad_hash
        self._good_hash = good_hash
        self._plot_data = plot_data
