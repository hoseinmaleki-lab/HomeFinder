import unittest
from bs4 import BeautifulSoup
from scripts.collect_public import parse_bentley, parse_location, dedupe, make_record, structured_records

class CollectorTests(unittest.TestCase):
    def test_town_is_separated_from_concatenated_address(self):
        self.assertEqual(parse_location("2110 Union Hill RoadMalvern, PA 19355"),
                         ("2110 Union Hill Road", "Malvern"))
    def test_bentley_table_excludes_sold_and_under_3000(self):
        sample = """
        <table>
          <tr><th>ADDRESS</th><th>ACRE</th><th>FLOOR PLAN</th><th>SQFT</th><th>STATUS</th><th>PRICE</th><th>DELIVERY</th></tr>
          <tr><td><a href="/listing/one">107 Palmetto Lane Devon, PA 19333</a></td><td>.55</td><td>Logan</td><td>4,014</td><td>Available</td><td>$2,499,900</td><td>Spring 2027</td></tr>
          <tr><td>837 Nathan Hale Road Berwyn, PA 19312</td><td>1.0</td><td>Chandler</td><td>5,082</td><td>SOLD</td><td>$2,849,900</td><td>Winter 2026</td></tr>
          <tr><td>1 Short Lane Wayne, PA 19087</td><td>.5</td><td>Custom</td><td>2,999</td><td>Available</td><td>$1,000,000</td><td>2027</td></tr>
        </table>"""
        items = parse_bentley(BeautifulSoup(sample, "html.parser"), "2026-11-10")
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]["address"], "107 Palmetto Lane")
        self.assertEqual(items[0]["price"], 2499900)
        self.assertEqual(items[0]["sqft"], 4014)
        self.assertEqual(items[0]["city"], "Devon")
    def test_deduplicate_same_address(self):
        a = make_record("A","100 Main St","Wayne",2000000,4000,"For Sale","https://example.com/one","2026-11-10")
        b = make_record("B","100 Main St","Wayne",2000000,4000,"For Sale","https://example.com/two","2026-11-10")
        items = dedupe([a,b])
        self.assertEqual(len(items),1)
        self.assertEqual(items[0]["also_listed_by"],["B"])
    def test_structured_listing_with_numeric_address(self):
        sample = """<script type="application/ld+json">
        {"@type":"SingleFamilyResidence","address":{"streetAddress":"218 Grays Ln","addressLocality":"Haverford","addressRegion":"PA"},
         "floorSize":{"value":4200,"unitCode":"FTK"},"offers":{"price":1250000},
         "numberOfBedrooms":5,"numberOfBathroomsTotal":4,
         "url":"https://example.com/homes/218-grays"}
        </script>"""
        source = {"name":"Test Brokerage","url":"https://example.com/listings"}
        items = structured_records(BeautifulSoup(sample,"html.parser"),source,"2026-11-10")
        self.assertEqual(len(items),1)
        self.assertEqual(items[0]["address"],"218 Grays Ln")
        self.assertEqual(items[0]["sqft"],4200)
        self.assertEqual(items[0]["price"],1250000)
    def test_excludes_out_of_area_and_small(self):
        self.assertIsNone(make_record("A","123 Main St","Philadelphia",1000000,5000,"For Sale","https://example.com","2026-11-10"))
        self.assertIsNone(make_record("A","123 Main St","Wayne",1000000,2000,"For Sale","https://example.com","2026-11-10"))

if __name__=="__main__":
    unittest.main()
