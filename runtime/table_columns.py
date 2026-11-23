"""Bounded PowerTable column presentation constructors from verified SQL metadata.

Portable columnConfigs records, not row-save metadata or SQL DDL. No default
database, connection, table, lookup, access grant or existing record GUID.
"""
import copy
from .construct import guid

def column_config(column, kind, *, lookup=None, lookup_catalog=None, decimals=2, allow_negative=True, allow_edit=None):
    if kind not in ('integer','decimal','date','database-lookup','text-options'): raise ValueError('Unimplemented column kind')
    name=column['name'];db=copy.deepcopy(column['dbMeta'])
    required={'type','isIdentity','isNullable','isPrimaryKey','isUnique','isCompositeUnique'}
    if not isinstance(name,str) or not name or not required<=db.keys(): raise ValueError('Complete physical SQL metadata required')
    if any(not isinstance(db[k],bool) for k in required-{'type'}): raise ValueError('SQL metadata Boolean required')
    sqltype=db['type'].lower();identity=db['isIdentity'];pk=db['isPrimaryKey']
    if allow_edit is not None and not isinstance(allow_edit,bool):raise ValueError('allow_edit must be Boolean')
    if identity and allow_edit is True:raise ValueError('Database identity columns must remain read-only')
    compatible={'integer':{'int','bigint','smallint','tinyint','bit'},'decimal':{'decimal','numeric','money','smallmoney','float','real'},
                'date':{'date','datetime','datetime2','smalldatetime'},'database-lookup':{'int','bigint','smallint','tinyint','varchar','nvarchar','char','nchar'},
                'text-options':{'varchar','nvarchar','char','nchar'}}
    if sqltype not in compatible[kind]: raise ValueError('SQL type incompatible with selected presentation kind')
    if kind!='database-lookup' and (lookup is not None or lookup_catalog is not None): raise ValueError('Lookup supplied to nonlookup column')
    meta={'dbMeta':db,'defaultValue':'','defaultValueType':'NONE','isPrimaryKey':pk,
          'resetToDefaultOnRowModify':False,'updateValueOnRowModify':False}
    result={'allowEdit':0 if identity or allow_edit is False else 1,'columnGuid':name,'columnName':name,
            'columnType':{'integer':6,'decimal':13,'date':4,'database-lookup':2,'text-options':2}[kind],
            'visualColumnType':3 if kind in ('database-lookup','text-options') else 1,'description':'','displayName':name,
            'hideColumn':1 if identity else 0,'mandatory':0 if identity or db['isNullable'] else 1,
            'recordGuid':guid(),'columnMeta':meta}
    if kind in ('integer','decimal'):
        if not isinstance(allow_negative,bool): raise ValueError('allow_negative must be Boolean')
        meta.update(allowNegative=allow_negative,largeNumberAbbrevation='',max='',min='',negativeValueFormat='-0',prefix='',suffix='',thousandSeparator='')
        if kind=='decimal':
            if isinstance(decimals,bool) or not isinstance(decimals,int) or not 0<=decimals<=15: raise ValueError('Invalid decimals')
            meta['noOfDecimals']=decimals
    elif kind=='date':meta.update(format='DEFAULT_LOCALE',min='',max='')
    elif kind=='text-options':
        meta.update(allowAddingNewOptions=True,fcVisualIdColumnName=None,fcVisualLabelColumnName=None,
                    fcVisualName=None,isFilterBasedOnAnotherValue=False,optionLinking={},options=[],selectionMethod='DISTINCT_VALUES')
    else:
        if identity or not isinstance(lookup,dict) or not isinstance(lookup_catalog,list): raise ValueError('Lookup specification and current SQL catalog required')
        if not {'schema','table','key','label'}<=lookup.keys() or set(lookup)-{'schema','table','key','label','chain'}:
            raise ValueError('Explicit lookup schema/table/key/label required; optional chain only')
        chain=lookup.get('chain',[])
        if not isinstance(chain,list):raise ValueError('Lookup chain must be an ordered list')
        hops=[{k:v for k,v in lookup.items() if k!='chain'},*chain]
        records=[];previous=None
        for order,hop in enumerate(hops):
            required={'schema','table','key','label'}|({'column'} if order else set())
            if not isinstance(hop,dict) or set(hop)!=required or any(not isinstance(hop[k],str) or not hop[k].strip() for k in required):
                raise ValueError('Incomplete lookup hop')
            local_name=name if order==0 else hop['column']
            if order and local_name not in previous:raise ValueError('Chained key absent from preceding lookup table')
            local_type=sqltype if order==0 else previous[local_name]['type'].lower()
            tables=[t for t in lookup_catalog if t['schema']==hop['schema'] and t['table']==hop['table']]
            if len(tables)!=1: raise ValueError('Missing/ambiguous lookup table')
            columns=tables[0]['columns'];names=[c['name'] for c in columns]
            if len(names)!=len(set(names)): raise ValueError('Ambiguous lookup column')
            by_name={c['name']:c for c in columns}
            if hop['key'] not in by_name or hop['label'] not in by_name: raise ValueError('Lookup key/label absent from SQL metadata')
            key=by_name[hop['key']]
            if key['type'].lower()!=local_type or not (key.get('isPrimaryKey') is True or key.get('isUnique') is True):
                raise ValueError('Lookup requires compatible unique remote key')
            records.append({'id':local_name,'label':hop['label'],'linkingColumn':hop['key'],
                            'order':order,'schema':hop['schema'],'table':hop['table']})
            previous=by_name
        result['displayName']=lookup['label']
        meta.update(optionLinking={'lookupConfig':records},options=[],selectionMethod='LOAD_FROM_DATABASE',
                    allowAddingNewOptions=False,isFilterBasedOnAnotherValue=False)
    return result

def apply_lookup(column,lookup,lookup_catalog):
    """Change lookup presentation only; preserve IDs, locks, dbMeta and row values."""
    generated=column_config({'name':column['columnName'],'dbMeta':column['columnMeta']['dbMeta']},
                            'database-lookup',lookup=lookup,lookup_catalog=lookup_catalog)
    result=copy.deepcopy(column)
    for key in ('columnType','visualColumnType','displayName'):result[key]=generated[key]
    for key in ('optionLinking','options','selectionMethod','allowAddingNewOptions','isFilterBasedOnAnotherValue'):
        result['columnMeta'][key]=copy.deepcopy(generated['columnMeta'][key])
    return result
