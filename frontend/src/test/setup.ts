// Node >= 25 expone un localStorage global (inutilizable sin --localstorage-file) que tapa
// el de jsdom. Si no es un Storage funcional, se instala uno en memoria para los tests.
if (typeof globalThis.localStorage?.clear !== "function") {
  const data = new Map<string, string>();
  const memoryStorage: Storage = {
    get length() {
      return data.size;
    },
    clear: () => data.clear(),
    getItem: (key) => data.get(key) ?? null,
    key: (index) => Array.from(data.keys())[index] ?? null,
    removeItem: (key) => void data.delete(key),
    setItem: (key, value) => void data.set(key, String(value)),
  };
  Object.defineProperty(globalThis, "localStorage", { value: memoryStorage, configurable: true });
}
