import pathlib
p = pathlib.Path(r"C:/Users/Administrator/Desktop/YQ/frontend/src/components/AppLayout.vue")
c = p.read_text("utf-8")

# 1. Add keywords/sources nav items before propagation
old_nav = '<router-link to="/propagation" class="nav-item"'
new_nav = '<router-link to="/keywords" class="nav-item" :class="{ active: activeMenu === '
new_nav += "'/keywords' }" + '">\n          <span class="ico">\u2637</span><span>\u5173\u952e\u8bcd\u7ba1\u7406</span>\n        </router-link>\n        <router-link to="/sources" class="nav-item" :class="{ active: activeMenu === '
new_nav += "'/sources' }" + '">\n          <span class="ico">\u2604</span><span>\u6570\u636e\u6e90\u7ba1\u7406</span>\n        </router-link>\n        <router-link to="/propagation" class="nav-item"'
c = c.replace(old_nav, new_nav)

# 2. Update activeMenu
c = c.replace(
    "if (route.path.startsWith('/event')) return '/events'",
    "if (route.path.startsWith('/event')) return '/events'\n  if (route.path.startsWith('/keyword')) return '/keywords'\n  if (route.path.startsWith('/source')) return '/sources'"
)

# 3. Add page titles
c = c.replace(
    "'/propagation': '\u4f20\u64ad\u6eaf\u6e90',",
    "'/propagation': '\u4f20\u64ad\u6eaf\u6e90',\n    '/keywords': '\u5173\u952e\u8bcd\u7ba1\u7406',\n    '/sources': '\u6570\u636e\u6e90\u7ba1\u7406',"
)

# 4. Add page subtitles
c = c.replace(
    "'/propagation': '\u6eaf\u6e90\u5206\u6790\u8206\u60c5\u4f20\u64ad\u8def\u5f84',",
    "'/propagation': '\u6eaf\u6e90\u5206\u6790\u8206\u60c5\u4f20\u64ad\u8def\u5f84',\n    '/keywords': '\u7ba1\u7406\u8206\u60c5\u5173\u952e\u8bcd\u5e93\uff0c\u652f\u6301\u5206\u7c7b\u4e0e\u6743\u91cd',\n    '/sources': '\u67e5\u770b\u5404\u6570\u636e\u6e90\u72b6\u6001\u4e0e\u91c7\u96c6\u5386\u53f2',"
)

p.write_text(c, "utf-8")
print(f"Updated: {len(c)} bytes")
print(f"Has keywords nav: {'<router-link to=\"/keywords\"' in c}")
print(f"Has sources nav: {'<router-link to=\"/sources\"' in c}")