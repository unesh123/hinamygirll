try:
    raise ValueError('test')
except TypeError, ValueError, KeyError:
    print('CAUGHT')
except Exception as e:
    print('MISSED:', repr(e))
