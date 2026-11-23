"""Direct semantic Values: numeric columns default to Sum, DAX stays a measure.

Source aggregation is independent of Planning row/column total aggregation.
Use this for new bindings; never rehash existing persisted measure identities.
"""
NUMERIC = {'Int64', 'Double', 'Decimal'}
AGGREGATIONS = {'sum', 'average', 'min', 'max', 'count'}


def source_aggregation(value=None):
    if value is None:
        return 'sum'
    if not isinstance(value, str):
        raise ValueError('Source aggregation must be a supported string')
    value = value.casefold()
    value = {'avg': 'average', 'minimum': 'min', 'maximum': 'max'}.get(value, value)
    if value not in AGGREGATIONS:
        raise ValueError('Unsupported semantic source aggregation: ' + value)
    return value


def semantic_value(model, key, registry, *, bucket='ameasure', order=0,
                   label=None, aggregation=None):
    from .construct import field
    if bucket not in ('ameasure', 'AC', 'PY'):
        raise ValueError('Use a Values bucket for a semantic value')
    a = field(model, key, 'ameasure', order)
    if a['dataType'] not in NUMERIC:
        raise ValueError('Direct Values assignment requires a numeric model field')
    if a['columnType'] == 'Measure':
        if aggregation is not None:
            raise ValueError('Do not reaggregate an explicit DAX measure')
        a['measureGuid'] = registry.semantic(key, 'Measure')
    elif a['columnType'] == 'Column':
        method = source_aggregation(aggregation)
        a.update(aggregationType=method, customSource=True,
                 measureGuid=registry.semantic(key, 'Column', method))
    else:
        raise ValueError('Resolve a model Column or explicit DAX Measure')
    a['bucketId'] = bucket
    if label is not None:
        a['customName'] = label
    return a
