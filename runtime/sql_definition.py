"""Read physical SQL table definitions through the authorized Fabric item API.

This is metadata export only: no SQL token, connection creation, DDL or row write.
The official API requires SQL database read/write permission. A successful SQL
project export establishes schema, not PowerTable credential or row-save access.
"""
import base64,re
from pathlib import PurePosixPath

def read_sql_project(client,workspace,database,label):
    response=client.request('POST',f'/workspaces/{workspace}/sqlDatabases/{database}/getDefinition?format=sqlproj',label=label)
    envelope=client.finish(response,label)['body']
    parts=envelope.get('definition',envelope).get('parts',[]);decoded={}
    if not parts:raise ValueError('SQL project definition is empty')
    for part in parts:
        path=PurePosixPath(part['path'])
        if path.is_absolute() or '..' in path.parts or '\\' in str(path) or ':' in str(path):raise ValueError('Unsafe SQL project path')
        if part.get('payloadType')!='InlineBase64':raise ValueError('Unsupported SQL project payload')
        if str(path) in decoded:raise ValueError('Duplicate SQL project part')
        decoded[str(path)]=base64.b64decode(part['payload'],validate=True).decode('utf-8-sig')
    return envelope,decoded

def physical_table(sql,schema,table):
    """Conservative parser for captured ordinary INT/BIT/DATE/text/decimal tables.

    Additional SQL syntax fails instead of inventing key/identity/null metadata.
    Constraints remain database-owned and are retained in the exported SQL text.
    """
    prefix=f'CREATE TABLE [{schema}].[{table}]'
    if not sql.lstrip().startswith(prefix):raise ValueError('Expected physical CREATE TABLE definition')
    pk_match=re.search(r'PRIMARY KEY (?:CLUSTERED|NONCLUSTERED) \(([^)]+)\)',sql)
    if not pk_match:raise ValueError('Explicit primary key required')
    pk=re.findall(r'\[([^]]+)\]',pk_match[1]);unique=[re.findall(r'\[([^]]+)\]',g) for g in re.findall(r'UNIQUE (?:CLUSTERED|NONCLUSTERED) \(([^)]+)\)',sql)]
    lines=[s for s in sql.splitlines() if re.match(r'^\s+\[[^]]+\]\s+',s)]
    columns=[]
    for line in lines:
        match=re.match(r'^\s+\[([^]]+)\]\s+(INT|BIT|DATE|NVARCHAR|DECIMAL)\b\s*(\([^)]*\))?(.*)',line)
        if not match:raise ValueError('Unsupported physical SQL column syntax')
        name,typ,size,tail=match.groups()
        if not re.fullmatch(r'\s*(?:IDENTITY\s*\(\d+,\s*\d+\)\s*)?(?:NOT NULL|NULL),?\s*',tail):raise ValueError('Unparsed physical SQL column attributes')
        meta={'type':typ.lower(),'isIdentity':'IDENTITY' in tail,'isNullable':'NOT NULL' not in tail,
          'isPrimaryKey':name in pk,'isUnique':any(g==[name] for g in unique),'isCompositeUnique':any(name in g and len(g)>1 for g in unique)}
        if typ=='DECIMAL':
            values=[int(x) for x in re.findall(r'\d+',size or '')]
            if len(values)!=2:raise ValueError('Decimal precision and scale required')
            meta.update(zip(['numericPrecision','numericScale'],values))
        if typ=='NVARCHAR':
            if not size or not re.fullmatch(r'\(\d+\)',size):raise ValueError('Explicit finite text length required')
            meta['maxLength']=2*int(size[1:-1])
        columns.append({'name':name,'dbMeta':meta})
    names=[x['name'] for x in columns]
    if not columns or len(names)!=len(set(names)) or not set(pk)<=set(names):raise ValueError('Incomplete physical schema')
    return {'schema':schema,'name':table,'physicalType':'U','primaryKey':pk,'columns':columns}
