import pathlib
al = pathlib.Path(r"C:/Users/Administrator/Desktop/YQ/frontend/src/components/AppLayout.vue")
raw = al.read_bytes()
ns = raw.find(b'<nav class=')
ne = raw.find(b'</nav>', ns) + 6
correct = b'      <nav class="nav">\n        <router-link to="/dashboard" class="nav-item" :class="{ active: activeMenu === '
correct += b"'" + b'/dashboard' + b"'" + b' }">\n          <span class="ico">\xe2\x96\xa4</span><span>\xe9\xa9\xbe\xe9\xa9\xb6\xe8\x88\xb1</span>\n        </router-link>\n        <router-link to="/opinions" class="nav-item" :class="{ active: activeMenu === '
correct += b"'" + b'/opinions' + b"'" + b' }">\n          <span class="ico">\xe2\x98\xb0</span><span>\xe8\x88\x86\xe6\x83\x85\xe5\x88\x97\xe8\xa1\xa8</span>\n        </router-link>\n        <router-link to="/events" class="nav-item" :class="{ active: activeMenu === '
correct += b"'" + b'/events' + b"'" + b' }">\n          <span class="ico">\xe2\x9a\xa0</span><span>\xe4\xba\x8b\xe4\xbb\xb6\xe4\xb8\xad\xe5\xbf\x83</span>\n        </router-link>\n        <router-link to="/alerts" class="nav-item" :class="{ active: activeMenu === '
correct += b"'" + b'/alerts' + b"'" + b' }">\n          <span class="ico">!</span><span>\xe9\xa2\x84\xe8\xad\xa6\xe4\xb8\xad\xe5\xbf\x83</span>\n        </router-link>\n        <router-link to="/keywords" class="nav-item" :class="{ active: activeMenu === '
correct += b"'" + b'/keywords' + b"'" + b' }">\n          <span class="ico">\xe2\x98\xb7</span><span>\xe5\x85\xb3\xe9\x94\xae\xe8\xaf\x8d\xe7\xae\xa1\xe7\x90\x86</span>\n        </router-link>\n        <router-link to="/sources" class="nav-item" :class="{ active: activeMenu === '
correct += b"'" + b'/sources' + b"'" + b' }">\n          <span class="ico">\xe2\x9c\xb4</span><span>\xe6\x95\xb0\xe6\x8d\xae\xe6\xba\x90\xe7\xae\xa1\xe7\x90\x86</span>\n        </router-link>\n        <router-link to="/propagation" class="nav-item" :class="{ active: activeMenu === '
correct += b"'" + b'/propagation' + b"'" + b' }">\n          <span class="ico">\xe2\x9c\xb4</span><span>\xe4\xbc\xa0\xe6\x92\xad\xe6\xba\xaf\xe6\xba\x90</span>\n        </router-link>\n      </nav>'
fixed = raw[:ns] + correct + raw[ne:]
al.write_bytes(fixed)
print(f"OK {len(raw)} -> {len(fixed)}")