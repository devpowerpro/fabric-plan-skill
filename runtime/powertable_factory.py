"""Existing-table initialization and bounded insert/update serialization.

Delete/upsert/replaceAll/distribute and audits/approvals require their full
operation contracts and are not silently mapped to ordinary row saves.
"""
import os,subprocess,copy,math
from decimal import Decimal
from pathlib import Path
from .codec import dumps
from .surfaces import powertable_source

def configured_table(name, table, connection, columns, *, explicit=False, allow_add=True, allow_update=True, allow_delete=False):
    """Complete ALM grid from verified target source/schema; no old report/template.

    SQL rows are never changed by this constructor. Row actions reflect the
    authorized maintenance scope and still require effective runtime access.
    """
    from .construct import guid,schema,sheet_properties
    from .codec import load
    if not columns or len({c['columnName'] for c in columns})!=len(columns):
        raise ValueError('Complete unique physical column configurations required')
    for c in columns:
        if not {'columnName','columnGuid','columnMeta','columnType','recordGuid'}<=c.keys():
            raise ValueError('Use column_config with physical SQL metadata')
    if any(not isinstance(x,bool) for x in (allow_add,allow_update,allow_delete)):
        raise ValueError('Row-action flags must be Boolean')
    source=powertable_source(table,connection,explicit)
    source['source'].update(creationMode=2,tableType=1)
    sid,vid=guid(),guid();prefix=f'sheets/{sid}/visuals/{vid}/'
    state=load(Path(__file__).resolve().parents[1]/'fixtures/powertable-presentation-defaults.json')
    names=[c['columnName'] for c in columns]
    state.update(columnMeta={n:{'width':210 if n.endswith('Name') else 150} for n in names},
        manageMeasures=[{'id':n,'label':n,'measureType':'data','name':n,'order':i,'visible':True} for i,n in enumerate(names)],
        assignmentColumnMap={},superFilterAssignments=[],superFilter={},newOptionsForSelectPersisted={},
        pivotPersistProperties={},superFilterMetaConfig={'orderedFilterIds':[]},
        embeddedSuperFilter={'incomingFilterAssignments':[],'superFilterAssignments':[]},
        groupingColumn=None,sortingColumn=None)
    props={'visualType':30,'pivotAssignments':[],'superFilterAssignments':[],'visualState':state,
        'position':{'x':0,'y':0},'dimension':{'width':1,'height':1},'visualInteractions':{},'lockAspectRatio':False}
    raw={f'sheets/{sid}/sheet.json':sheet_properties(),
        prefix+'properties.json':{'$schema':schema('PowerTable/Properties'),'properties':{'schema':'0.0.1','properties':props}},
        prefix+'source.json':source,
        prefix+'columnConfigs.json':{'$schema':schema('PowerTable/ColumnConfigs'),'columnConfigs':copy.deepcopy(columns)},
        prefix+'sourceSettings.json':{'$schema':schema('PowerTable/Settings'),'sourceSettings':[
            {'name':action,'recordGuid':guid(),'sourceId':source['source']['recordGuid'],'settings':{'enabled':enabled}}
            for action,enabled in [('ROW_ADD',allow_add),('ROW_UPDATE',allow_update),('ROW_DELETE',allow_delete)]]}}
    declaration={'recordGuid':sid,'displayName':name,'sheetType':'POWERTABLE','isHidden':False,
        'workloadItemEntityVisuals':[{'visualId':vid,'visualType':'POWERTABLE','isEmbedded':False}]}
    return declaration,raw,{'sheetGuid':sid,'visualGuid':vid,'sourceGuid':source['source']['recordGuid'],
        'sqlSchemaReadback':'required','rowSave':'not-tested'}

def existing_source(table,connection,explicit=False):
    # The initialization request is not a complete exported source.json. Its
    # response must be reconciled before ALM construction; do not invent labels.
    s=powertable_source(table,connection,explicit,require_metadata=False)['source']
    return {'tableName':s['tableName'],'schema':s['schemaName'],'dbName':s['dbName'],'dbHost':s['dbHost'],
        'connectionId':s['connectionId'],'creationMode':2,'sqlTargetArtifact':s['sqlTargetArtifact']}

def compress_json(value,node=None):
    node=node or os.environ.get('FABRIC_PLAN_NODE') or os.environ.get('FABRIC_PLAN_HTTP_NODE')
    if not node:raise ValueError('Set Node path for bundled LZUTF8 encoder')
    result=subprocess.run([node,str(Path(__file__).resolve().parents[1]/'tools/encode-lzutf8.cjs')],
      input=dumps(value),text=True,encoding='utf-8',capture_output=True,timeout=30)
    if result.returncode:raise ValueError('LZUTF8 encoding failed')
    return result.stdout.strip()

def row_save(metadata,operation,records,*,conditions=None,visual_meta=None,relations=None,generated_keys=(),node=None):
    if operation not in ('insert','update'):raise ValueError('Only explicit insert/update contracts implemented')
    if not isinstance(metadata,list) or not metadata or not isinstance(records,list) or not records:raise ValueError('Metadata and records required')
    ids=[]
    for m in metadata:
        if not isinstance(m,dict) or not isinstance(m.get('id'),str) or not m['id']:raise ValueError('Column identity required')
        if set(m)-{'id','dataType','isPrimaryKey','isNullable','isEditable','isCustomColumn'}:raise ValueError('Unknown metadata field')
        for k in ('isPrimaryKey','isNullable','isEditable','isCustomColumn'):
            if k in m and not isinstance(m[k],bool):raise ValueError('Metadata Boolean')
        ids.append(m['id'])
    if len(ids)!=len(set(ids)):raise ValueError('Duplicate metadata column')
    if any(m.get('isCustomColumn') for m in metadata) and not relations:raise ValueError('Lookup relation metadata required')
    if not isinstance(visual_meta,dict) or not {'rowIds','optionsMeta'}<=visual_meta.keys():raise ValueError('Actual visual/audit metadata required')
    row_ids=visual_meta['rowIds']
    allowed_counts={0,len(records)} if operation=='insert' else {len(records)}
    if not isinstance(row_ids,list) or len(row_ids) not in allowed_counts or any(not isinstance(x,(str,int)) or isinstance(x,bool) for x in row_ids) or len({str(x) for x in row_ids})!=len(row_ids):raise ValueError('Unique scalar row identities required; create may have an empty identity array')
    if not isinstance(visual_meta['optionsMeta'],dict):raise ValueError('Options metadata must be an object')
    def scalar(value,meta):
        if value is None:
            if meta.get('isNullable') is False:raise ValueError('Null value in nonnullable column: '+meta['id'])
            return
        if not isinstance(value,(str,int,float,bool,Decimal)):raise ValueError('Expected scalar row value')
        if isinstance(value,float) and not math.isfinite(value) or isinstance(value,Decimal) and not value.is_finite():raise ValueError('Nonfinite row value')
    if operation=='insert':
        omitted=[m['id'] for m in metadata if m.get('isPrimaryKey') and not m.get('isEditable',True)]
        if set(omitted)!=set(generated_keys):raise ValueError('Verify every omitted noneditable key is database generated')
        exported=[m for m in metadata if m['id'] not in omitted]
        for r in records:
            if not isinstance(r,list) or len(r)!=len(exported):raise ValueError('Insert row must match exported metadata order')
            for value,m in zip(r,exported):scalar(value,m)
        inner={'createData':{'records':copy.deepcopy(records),'visualMeta':copy.deepcopy(visual_meta)}}
    else:
        exported=metadata;keys={m['id'] for m in metadata if m.get('isPrimaryKey')}
        if not keys or not isinstance(conditions,list) or len(conditions)!=len(records):raise ValueError('Update key conditions required for every record')
        if not {'oldRecords','updatedColumns'}<=visual_meta.keys():raise ValueError('Update audit metadata required')
        if not isinstance(visual_meta['oldRecords'],list) or len(visual_meta['oldRecords']) not in (0,len(records)) or any(not isinstance(r,dict) for r in visual_meta['oldRecords']):raise ValueError('Old records must be empty or contain one object per update')
        changed_columns=visual_meta['updatedColumns']
        if not isinstance(changed_columns,list) or any(not isinstance(k,str) for k in changed_columns) or len(set(changed_columns))!=len(changed_columns):raise ValueError('Unique updated-column names required')
        if len({dumps(c) for c in conditions})!=len(conditions):raise ValueError('Duplicate update key conditions')
        changed=set()
        for row,condition in zip(records,conditions):
            if not isinstance(condition,dict) or set(condition)!=keys or any(v is None for v in condition.values()):raise ValueError('Complete non-null primary-key condition required')
            for key,value in condition.items():scalar(value,next(m for m in metadata if m['id']==key))
            if not isinstance(row,dict) or not row or not set(row)<=set(ids) or set(row)&keys:raise ValueError('Update record names/keys')
            if any(not next(m for m in metadata if m['id']==k).get('isEditable',True) for k in row):raise ValueError('Noneditable column update')
            for key,value in row.items():scalar(value,next(m for m in metadata if m['id']==key))
            changed|=set(row)
        if set(visual_meta['updatedColumns'])!=changed:raise ValueError('Updated-column metadata differs from records')
        inner={'updateData':{'records':copy.deepcopy(records),'conditions':copy.deepcopy(conditions),'visualMeta':copy.deepcopy(visual_meta)}}
    return {'data':compress_json(inner,node),'metaData':copy.deepcopy(exported),'relations':copy.deepcopy(relations or {}),
        'incomingRowCount':len(records),'actions':[operation],'scdConfig':None}
