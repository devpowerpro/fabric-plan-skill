import copy, unittest
from runtime.powertable_readiness import inspect_native, require_configured

class PowerTableReadinessTests(unittest.TestCase):
 def setUp(self):
  self.entity={'id':'14','entityType':30,'displayName':'Employee Master'}
  self.page={'statusCode':200,'payload':{'visuals':[{'id':'61','visualType':30,'originEntityId':14,'dataSourceId':7,
   'properties':{'properties':{'pivotAssignments':[],'visualState':{'columnMeta':{'EmployeeID':{}}}}}}]}}
 def test_blank_is_not_complete(self):
  self.page['payload']['visuals']=[]
  r=inspect_native(self.entity,self.page)
  self.assertEqual(r['state'],'sheet-only-uninitialized')
  with self.assertRaises(ValueError):require_configured(r)
 def test_empty_chart_assignments_do_not_invalidate_powertable(self):
  r=require_configured(inspect_native(self.entity,self.page))
  self.assertTrue(r['configured']);self.assertEqual(r['rendered'],'not-tested');self.assertEqual(r['writeback'],'not-tested')
 def test_visual_without_source_is_incomplete(self):
  self.page['payload']['visuals'][0]['dataSourceId']=None
  self.assertFalse(inspect_native(self.entity,self.page)['configured'])
 def test_visual_without_columns_is_incomplete(self):
  self.page['payload']['visuals'][0]['properties']['properties']['visualState']['columnMeta']={}
  self.assertFalse(inspect_native(self.entity,self.page)['configured'])
 def test_wrong_owner_rejected(self):
  self.page['payload']['visuals'][0]['originEntityId']=99
  with self.assertRaises(ValueError):inspect_native(self.entity,self.page)
 def test_duplicate_visual_rejected(self):
  self.page['payload']['visuals']*=2
  with self.assertRaises(ValueError):inspect_native(self.entity,self.page)
 def test_schema_mismatch_not_ignored(self):
  r=inspect_native(self.entity,self.page,schema_response={'statusCode':200,'payload':[{'name':'EmployeeID'},{'name':'Salary'}]})
  self.assertEqual(r['schemaRead'],'configuration-mismatch');self.assertEqual(r['unconfiguredPhysicalColumns'],['Salary'])
 def test_schema_success_is_not_row_access(self):
  r=inspect_native(self.entity,self.page,schema_response={'statusCode':200,'payload':[{'name':'EmployeeID'}]})
  self.assertEqual(r['schemaRead'],'passed');self.assertEqual(r['writeback'],'not-tested')
