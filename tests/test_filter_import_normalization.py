import unittest,copy
from runtime.chart_filters import ensure_chart_filters,audit_chart_filters

class FilterImportNormalization(unittest.TestCase):
    def props(self):
        return ensure_chart_filters({'pivotAssignments':[{'id':'Sales[Actual]','sourceId':'Sales[Actual]',
            'sourceType':'PowerBI','bucketId':'AC','columnName':'Actual','tableName':'Sales',
            'columnType':'Measure','dataType':'Double','dataRoleType':'Measure'}]})
    def test_native_added_semantic_flag_is_not_a_missing_filter(self):
        p=self.props();p['pivotAssignments'][0]['customSource']=True
        self.assertEqual(audit_chart_filters(p)['visibleFieldFilters'],1)
    def test_false_flag_or_changed_identity_is_not_normalized(self):
        p=self.props();p['pivotAssignments'][0]['customSource']=False
        with self.assertRaises(ValueError):audit_chart_filters(p)
        p=self.props();p['superFilterAssignments'][0]['pivotAssignments'][0]['sourceId']='Other[Actual]'
        with self.assertRaises(ValueError):audit_chart_filters(p)
