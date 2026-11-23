"""Read-only PowerTable initialization evidence; never equate a sheet with a grid.

Inputs are the current item's native entity/page response and, optionally, the
table/schema response fetched in the returned source's actual visual context.
This module does not infer database access or rendering from property presence.
"""

def inspect_native(entity, page, *, schema_response=None):
    if entity.get('entityType') != 30:
        raise ValueError('Expected native PowerTable entity type 30')
    body = page.get('body', page)
    if body.get('statusCode') != 200 or not isinstance(body.get('payload', {}).get('visuals'), list):
        raise ValueError('Successful native page readback required')
    visuals = body['payload']['visuals']
    result = {'sheetId': str(entity['id']), 'sheetName': entity['displayName'],
              'state': 'sheet-only-uninitialized', 'configured': False,
              'sourceId': None, 'visualId': None, 'configuredColumns': [],
              'schemaRead': 'not-tested', 'rendered': 'not-tested', 'writeback': 'not-tested'}
    if not visuals:
        result['missing'] = ['PowerTable visual', 'source binding', 'column configuration']
        return result
    candidates = [v for v in visuals if v.get('visualType') == 30 and not v.get('isEmbedded')]
    if len(candidates) != 1:
        raise ValueError('Expected one directly owned PowerTable visual; reconcile actual inventory')
    v = candidates[0]
    if str(v.get('originEntityId')) != str(entity['id']):
        raise ValueError('PowerTable visual owner mismatch')
    result.update(visualId=str(v['id']), sourceId=v.get('dataSourceId'))
    source_id = v.get('dataSourceId')
    source_present = not isinstance(source_id, bool) and source_id is not None and str(source_id) not in ('', '0')
    props = v.get('properties', {}).get('properties', {})
    meta = props.get('visualState', {}).get('columnMeta', {})
    names = sorted(meta) if isinstance(meta, dict) else []
    result['configuredColumns'] = names
    result['missing'] = ([] if source_present else ['source binding']) + ([] if names else ['column configuration'])
    result['configured'] = not result['missing']
    result['state'] = 'visual-source-columns-registered' if result['configured'] else 'visual-incomplete'
    if schema_response is not None:
        sb = schema_response.get('body', schema_response)
        cols = sb.get('payload')
        if schema_response.get('status', 200) != 200 or sb.get('statusCode') != 200 or not isinstance(cols, list) or not cols:
            result['schemaRead'] = 'failed-or-empty'
        else:
            physical = [c.get('name') for c in cols]
            if not all(isinstance(n, str) and n for n in physical) or len(set(physical)) != len(physical):
                raise ValueError('Invalid or duplicate physical column names')
            result['physicalColumns'] = physical
            result['unconfiguredPhysicalColumns'] = sorted(set(physical) - set(names))
            result['schemaRead'] = 'passed' if not result['unconfiguredPhysicalColumns'] else 'configuration-mismatch'
    return result

def require_configured(result):
    """Use only when claiming configured PowerTable completion, not as a Plan-wide gate."""
    if result.get('configured') is not True:
        raise ValueError('PowerTable is not configured: ' + result.get('sheetName', 'unknown sheet'))
    return result
