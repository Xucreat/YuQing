from app.services.region_catalog import region_catalog_items


def test_region_catalog_contains_nested_beijing_area():
    items = {item["code"]: item for item in region_catalog_items()}

    assert items["110000"] == {
        "code": "110000",
        "name": "北京市",
        "level": "province",
        "parent_code": None,
    }
    assert items["110112"]["name"] == "通州区"
    assert items["110112"]["parent_code"] == "110000"
    assert items["110112105"]["name"] == "张家湾镇"
    assert items["110112105"]["level"] == "street"
    assert items["110112105"]["parent_code"] == "110112"


def test_region_catalog_flattens_virtual_municipality_layer():
    items = {item["code"]: item for item in region_catalog_items()}

    assert "110100" not in items
    assert items["110101"]["parent_code"] == "110000"
    assert {"province", "city", "county", "street"} <= {
        item["level"] for item in items.values()
    }


def test_region_catalog_keeps_dachang_under_langfang():
    items = {item["code"]: item for item in region_catalog_items()}

    assert items["131028"]["name"] == "大厂回族自治县"
    assert items["131028"]["level"] == "county"
    assert items["131028"]["parent_code"] == "131000"
    assert items["131028100"]["name"] == "大厂镇"
    assert items["131028100"]["parent_code"] == "131028"
