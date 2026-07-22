# 中国省级行政区划 GeoJSON（指挥大屏地图资源）

## 文件
- `china-provinces.json` —— 中国省级行政区边界（FeatureCollection，34 个省级要素 + 南海诸岛）。

## 来源
- 阿里巴巴 DataV.GeoAtlas（数据可视化地理小工具）
- 下载地址：`https://geo.datav.aliyun.com/areas_v3/bound/100000_full.json`
- 官网入口：https://datav.aliyun.com/portal/school/atlas/area_selector
- 下载时间：2026-07-22

## 许可证 / 使用说明
- DataV.GeoAtlas 是阿里云 DataV 面向公众公开提供的行政区划边界数据服务，是 ECharts
  社区绘制中国地图长期以来的事实标准数据源，允许在可视化项目中免费使用。
- 该数据为行政边界示意数据，仅用于数据可视化展示，不作为权威测绘依据。
- 如需用于正式对外发布/出版物，请依据《地图管理条例》使用带审图号的标准地图，
  并在上线前由使用方复核合规性（本项目当前为内部大屏展示用途）。

## 与后端数据的匹配
- 本文件 `features[].properties.name` 使用官方全称：如「河北省」「北京市」
  「内蒙古自治区」「广西壮族自治区」「新疆维吾尔自治区」「台湾省」
  「香港特别行政区」「澳门特别行政区」等。
- 后端 `GET /api/dashboard/stats` 的 `regions[].region_name` 在 Phase 1 已完成
  省级上卷，返回值同为省级官方全称（如「河北省」），因此可与本地图直接按名称匹配。
- 前端**不做**任何市/县 → 省的映射，只消费后端已经上卷好的省级聚合结果。

## 更新方式
如需更新，重新执行：
```
curl -sSL "https://geo.datav.aliyun.com/areas_v3/bound/100000_full.json" -o china-provinces.json
```
