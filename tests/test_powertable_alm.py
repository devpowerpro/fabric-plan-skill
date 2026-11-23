import unittest
from pathlib import Path
from runtime.powertable_factory import configured_table
from runtime.table_columns import column_config
from runtime.validate import Schemas,check_powertable_parts,validate_plan
from runtime.codec import load
from runtime.construct import build

ROOT=Path(__file__).resolve().parents[1]

class PowerTableAlmTests(unittest.TestCase):
    def test_complete_parts_and_source_links_without_foreign_ids(self):
        table={'name':'DimTest','schema':'dbo','physicalType':'U','primaryKey':['Key'],'columns':['Key']}
        conn={'connectionId':'00000000-0000-4000-8000-000000000001','dbHost':'sql.example.invalid',
            'dbName':'Test','artifactId':'00000000-0000-4000-8000-000000000002',
            'workspaceId':'00000000-0000-4000-8000-000000000003',
            'connectionName':'Demo connection','workspaceName':'Demo workspace','dbDisplayName':'Demo SQL'}
        col=column_config({'name':'Key','dbMeta':{'type':'int','isIdentity':False,'isNullable':False,
            'isPrimaryKey':True,'isUnique':True,'isCompositeUnique':False}},'integer')
        sheet,parts,ids=configured_table('Test',table,conn,[col],explicit=True)
        self.assertEqual(len(sheet['workloadItemEntityVisuals']),1)
        self.assertEqual(len(parts),5)
        properties=next(v for k,v in parts.items() if k.endswith('/properties.json'))
        self.assertEqual(properties['properties']['properties']['visualState']['manageMeasures'][0]['id'],'Key')
        self.assertNotIn('originEntityId',properties['properties']['properties'])
        settings=next(v for k,v in parts.items() if k.endswith('/sourceSettings.json'))['sourceSettings']
        self.assertTrue(all(s['sourceId']==ids['sourceGuid'] for s in settings))
        self.assertEqual([s['settings']['enabled'] for s in settings],[True,True,False])
        self.assertEqual((col['mandatory'],col['hideColumn'],col['allowEdit']),(1,0,1))
        schema=Schemas()
        for v in parts.values():schema.check(v,v['$schema'])
        prefix=next(k.rsplit('properties.json',1)[0] for k in parts if k.endswith('/properties.json'))
        self.assertEqual(check_powertable_parts(parts,prefix),
            {'sourceId':ids['sourceGuid'],'columns':1,'settings':3})

    def test_source_and_column_identity_mismatches_are_rejected(self):
        table={'name':'DimTest','schema':'dbo','physicalType':'U','primaryKey':['Key'],'columns':['Key']}
        conn={'connectionId':'00000000-0000-4000-8000-000000000001','dbHost':'sql.example.invalid',
            'dbName':'Test','artifactId':'00000000-0000-4000-8000-000000000002',
            'workspaceId':'00000000-0000-4000-8000-000000000003',
            'connectionName':'Demo connection','workspaceName':'Demo workspace','dbDisplayName':'Demo SQL'}
        col=column_config({'name':'Key','dbMeta':{'type':'int','isIdentity':False,'isNullable':False,
            'isPrimaryKey':True,'isUnique':True,'isCompositeUnique':False}},'integer')
        _,parts,_=configured_table('Test',table,conn,[col],explicit=True)
        prefix=next(k.rsplit('properties.json',1)[0] for k in parts if k.endswith('/properties.json'))
        settings=parts[prefix+'sourceSettings.json']['sourceSettings']
        settings[0]['sourceId']='other'
        with self.assertRaises(ValueError):check_powertable_parts(parts,prefix)
        settings[0]['sourceId']=parts[prefix+'source.json']['source']['recordGuid']
        state=parts[prefix+'properties.json']['properties']['properties']['visualState']
        state['columnMeta']['Other']={'width':150}
        with self.assertRaises(ValueError):check_powertable_parts(parts,prefix)

    def test_full_plan_validation_checks_configured_powertable_companions(self):
        model=load(ROOT/'fixtures/model.json');spec=load(ROOT/'fixtures/capacity-spec.json')
        table={'name':'DimTest','schema':'dbo','physicalType':'U','primaryKey':['Key'],'columns':['Key']}
        conn={'connectionId':'00000000-0000-4000-8000-000000000001','dbHost':'sql.example.invalid',
            'dbName':'Test','artifactId':'00000000-0000-4000-8000-000000000002',
            'workspaceId':'00000000-0000-4000-8000-000000000003',
            'connectionName':'Demo connection','workspaceName':'Demo workspace','dbDisplayName':'Demo SQL'}
        col=column_config({'name':'Key','dbMeta':{'type':'int','isIdentity':False,'isNullable':False,
            'isPrimaryKey':True,'isUnique':True,'isCompositeUnique':False}},'integer')
        sheet,parts,_=configured_table('Test',table,conn,[col],explicit=True)
        built=build(model,spec);raw=built['raw'];raw['definition.json']['sheets'].append(sheet);raw.update(parts)
        self.assertEqual(validate_plan(raw)['sheets'],2)
