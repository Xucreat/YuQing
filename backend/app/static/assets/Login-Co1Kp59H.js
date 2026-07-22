import { d as defineComponent, u as useAuthStore, c as createElementBlock, a as createBaseVNode, w as withDirectives, v as vModelText, b as withKeys, t as toDisplayString, e as createTextVNode, r as ref, f as reactive, E as ElMessage, g as api, h as useRouter, o as openBlock, _ as _export_sfc } from './index-wCs4YKKO.js';

const _hoisted_1 = { class: "login-screen" };
const _hoisted_2 = { class: "login-card" };
const _hoisted_3 = { class: "field" };
const _hoisted_4 = { class: "field" };
const _hoisted_5 = ["disabled"];
const _sfc_main = /* @__PURE__ */ defineComponent({
  __name: "Login",
  setup(__props) {
    const router = useRouter();
    const authStore = useAuthStore();
    const loading = ref(false);
    const form = reactive({
      username: "admin",
      password: "admin123"
    });
    async function handleLogin() {
      if (!form.username.trim() || !form.password.trim()) {
        ElMessage.warning("请输入用户名和密码");
        return;
      }
      if (loading.value) return;
      loading.value = true;
      try {
        const { data } = await api.post("/login", {
          username: form.username,
          password: form.password
        });
        authStore.setToken(data.access_token);
        authStore.setUsername(form.username);
        authStore.setRole(data.role || "analyst");
        authStore.setPermissions(data.permissions || []);
        ElMessage.success("登录成功");
        router.push("/dashboard");
      } catch (err) {
        const msg = err?.response?.data?.detail || err?.message || "登录失败，请检查用户名或密码";
        ElMessage.error(typeof msg === "string" ? msg : "登录失败");
      } finally {
        loading.value = false;
      }
    }
    return (_ctx, _cache) => {
      return openBlock(), createElementBlock("div", _hoisted_1, [
        createBaseVNode("div", _hoisted_2, [
          _cache[4] || (_cache[4] = createBaseVNode("div", { class: "login-badge" }, "YQ", -1)),
          _cache[5] || (_cache[5] = createBaseVNode("h1", { class: "login-title" }, "大厂县公安互联网舆情监测研判平台", -1)),
          _cache[6] || (_cache[6] = createBaseVNode("p", { class: "login-sub" }, "Internet Public Opinion Monitoring Platform", -1)),
          createBaseVNode("div", _hoisted_3, [
            _cache[2] || (_cache[2] = createBaseVNode("label", null, "用户名", -1)),
            withDirectives(createBaseVNode("input", {
              "onUpdate:modelValue": _cache[0] || (_cache[0] = ($event) => form.username = $event),
              class: "input",
              type: "text",
              placeholder: "请输入用户名",
              autocomplete: "username",
              onKeyup: withKeys(handleLogin, ["enter"])
            }, null, 544), [
              [vModelText, form.username]
            ])
          ]),
          createBaseVNode("div", _hoisted_4, [
            _cache[3] || (_cache[3] = createBaseVNode("label", null, "密码", -1)),
            withDirectives(createBaseVNode("input", {
              "onUpdate:modelValue": _cache[1] || (_cache[1] = ($event) => form.password = $event),
              class: "input",
              type: "password",
              placeholder: "请输入密码",
              autocomplete: "current-password",
              onKeyup: withKeys(handleLogin, ["enter"])
            }, null, 544), [
              [vModelText, form.password]
            ])
          ]),
          createBaseVNode("button", {
            class: "btn btn-primary login-btn",
            disabled: loading.value,
            onClick: handleLogin
          }, toDisplayString(loading.value ? "登录中..." : "登 录"), 9, _hoisted_5),
          _cache[7] || (_cache[7] = createBaseVNode("p", { class: "login-hint" }, [
            createTextVNode(" 默认账号 "),
            createBaseVNode("code", null, "admin"),
            createTextVNode(" / "),
            createBaseVNode("code", null, "admin123")
          ], -1))
        ])
      ]);
    };
  }
});

const Login = /* @__PURE__ */ _export_sfc(_sfc_main, [["__scopeId", "data-v-6c94df06"]]);

export { Login as default };
