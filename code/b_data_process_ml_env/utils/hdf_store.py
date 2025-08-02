from collections import ChainMap
import pandas as pd
import numpy as np

def read_hdf_wideDf(filename, columns=None, **kwargs):
    """Read a `pandas.DataFrame` from a HDFStore.

    Parameter
    ---------
    filename : str
        name of the HDFStore
    columns : list
        the columns in this list are loaded. Load all columns, 
        if set to `None`.

    Returns
    -------
    data : pandas.DataFrame
        loaded data.

    """
    store = pd.HDFStore(filename)
    data = []
    try:
        colsTabNum = store.select('colsTabNum')
    except KeyError:
        colsTabNum = None
    if colsTabNum is not None:
        if columns is not None:
            tabNums = pd.Series(
                index=colsTabNum[columns].values,
                data=colsTabNum[columns].data).sort_index()
            for table in tabNums.unique():
                data.append(
                    store.select(table, columns=tabNums[table], **kwargs))
        else:
            for table in colsTabNum.unique():
                data.append(store.select(table, **kwargs))
        data = pd.concat(data, axis=1).sort_index(axis=1)
    else:
        data = store.select('data', columns=columns)
    store.close()
    return data

def wideDf_to_hdf(filename, data, columns=None, maxColSize=2000, **kwargs):
    """Write a `pandas.DataFrame` with a large number of columns
    to one HDFStore.

    Parameters
    -----------
    filename : str
        name of the HDFStore
    data : pandas.DataFrame
        data to save in the HDFStore
    columns: list
        a list of columns for storing. If set to `None`, all 
        columns are saved.
    maxColSize : int (default=2000)
        this number defines the maximum possible column size of 
        a table in the HDFStore.

    """
    try:
        store = pd.HDFStore(filename, **kwargs)
        if columns is None:
            columns = data.columns
        colSize = columns.shape[0]
        if colSize > maxColSize:
            numOfSplits = np.ceil(colSize / maxColSize).astype(int)
            colsSplit = [
                columns[i * maxColSize:(i + 1) * maxColSize]
                for i in range(numOfSplits)
            ]
            _colsTabNum = ChainMap(*[
                dict(zip(columns, ['data{}'.format(num)] * colSize))
                for num, columns in enumerate(colsSplit)
            ])
            colsTabNum = pd.Series(dict(_colsTabNum)).sort_index()
            for num, cols in enumerate(colsSplit):
                store.put('data{}'.format(num), data[cols], format='table')
            store.put('colsTabNum', colsTabNum, format='fixed')
        else:
            store.put('data', data[columns], format='table')
        store.close()
    except Exception as e:
        print(e)
        store.close()
        raise