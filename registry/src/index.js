import React from "react";
import ReactDOM from "react-dom/client";
import "./index.css";
import App from "./App";
import { CookiesProvider } from "react-cookie";
import { configureStore } from "@reduxjs/toolkit";
import { Provider } from "react-redux";
import rootReducer from "./store/reducers/rootReducer";
import { persistStore, persistReducer } from "redux-persist";
import storage from "redux-persist/lib/storage";
import { PersistGate } from "redux-persist/integration/react";
import { createTransform, REGISTER } from "redux-persist";

const authTransform = createTransform(
  // Transform state on its way to being serialized and stored
  (inboundState, key) => {
    return {
      isAuthenticated: inboundState.isAuthenticated,
      username: inboundState.username,
      uuid: inboundState.uuid,
    };
  },
  // Transform state on its way back from storage to be rehydrated
  (outboundState, key) => {
    return {
      ...outboundState,
    };
  },
  // Specify the key for the persistable state, in this case it is 'auth'
  { whitelist: ["auth"] }
);

const persistConfig = {
  key: "root",
  storage,
  transforms: [authTransform],
  whitelist: ["auth"],
};

const persistedReducer = persistReducer(persistConfig, rootReducer);

const root = ReactDOM.createRoot(document.getElementById("root"));
const store = configureStore({
  reducer: persistedReducer,
  middleware: (getDefaultMiddleware) =>
    getDefaultMiddleware({
      serializableCheck: {
        ignoreActions: [REGISTER],
      },
    }),
});

const persistor = persistStore(store);

root.render(
  <Provider store={store}>
    <PersistGate persistor={persistor}>
      <CookiesProvider>
        <App />
      </CookiesProvider>
    </PersistGate>
  </Provider>
  // </React.StrictMode>
);

// If you want to start measuring performance in your app, pass a function
// to log results (for example: reportWebVitals(console.log))
// or send to an analytics endpoint. Learn more: https://bit.ly/CRA-vitals
// reportWebVitals();
