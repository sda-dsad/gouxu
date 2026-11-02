import unittest,json
from pathlib import Path
import jsonschema
R=Path(__file__).resolve().parents[1]
class SceneContractTests(unittest.TestCase):
 def setUp(self):self.c=json.loads((R/'contracts/scene.contract.json').read_text())
 def test_orthographic(self):self.assertEqual(self.c['common']['projection'],'orthographic')
 def test_focus_not_scope(self):self.assertFalse(self.c['common']['focus_changes_scope'])
 def test_depth_is_not_third_metric(self):self.assertFalse(self.c['common']['depth_encodes_data'])
 def test_glow_is_not_purchase(self):self.assertFalse(self.c['common']['glow_encodes_data'])
 def test_equal_search_width(self):self.assertEqual(self.c['search']['width'],'constant')
 def test_equal_search_depth(self):self.assertEqual(self.c['search']['depth'],'constant')
 def test_height_starts_at_zero(self):self.assertEqual(self.c['common']['height_zero'],0)
 def test_two_metric_product_plane(self):self.assertEqual(self.c['products']['z'],'fixed data plane')
 def test_null_rate_contract(self):self.assertTrue(self.c['common']['nullable_rates'])
 def test_fixed_comparison_scale(self):self.assertEqual(self.c['compare']['domain'],[0,1]);self.assertFalse(self.c['compare']['independent_camera_autoscale'])
 def test_same_group_zero(self):self.assertEqual(self.c['compare']['same_group_difference'],0)
 def test_scope_threshold_independent(self):self.assertFalse(self.c['products']['threshold_changes_denominator'])
 def test_ui_schema(self):jsonschema.validate(json.loads((R/'fixtures/ui-state.example.json').read_text()),json.loads((R/'contracts/ui-state.schema.json').read_text()))
 def test_invalid_camera_rejected(self):
  d=json.loads((R/'fixtures/ui-state.example.json').read_text());d['camera']='freeflight'
  with self.assertRaises(jsonschema.ValidationError):jsonschema.validate(d,json.loads((R/'contracts/ui-state.schema.json').read_text()))
 def test_invalid_zoom_rejected(self):
  d=json.loads((R/'fixtures/ui-state.example.json').read_text());d['zoom']=100
  with self.assertRaises(jsonschema.ValidationError):jsonschema.validate(d,json.loads((R/'contracts/ui-state.schema.json').read_text()))
if __name__=='__main__':unittest.main()
