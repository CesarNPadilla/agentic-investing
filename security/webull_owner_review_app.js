"use strict";
const decode = value => Uint8Array.from(atob(value.replace(/-/g, "+").replace(/_/g, "/")), c => c.charCodeAt(0));
const encode = value => btoa(String.fromCharCode(...new Uint8Array(value))).replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/, "");
async function responseJson(response) {
  if (!response.ok) throw new Error("Review unavailable or rejected. No reset or trading was authorized.");
  return response.json();
}
let displayed;
const button = document.getElementById("sign");
const result = document.getElementById("result");
fetch("/review").then(responseJson).then(data => {
  displayed = data;
  document.getElementById("review").textContent = JSON.stringify(data, null, 2);
  button.disabled = false;
}).catch(error => { result.textContent = error.message; });
button.addEventListener("click", async () => {
  button.disabled = true;
  try {
    const options = await responseJson(await fetch("/begin", {
      method: "POST", headers: {"X-Owner-Review-Sha256": displayed.digest}
    }));
    options.publicKey.challenge = decode(options.publicKey.challenge);
    options.publicKey.allowCredentials.forEach(item => { item.id = decode(item.id); });
    const credential = await navigator.credentials.get(options);
    const assertion = {
      id: credential.id, rawId: encode(credential.rawId), type: credential.type,
      response: {
        clientDataJSON: encode(credential.response.clientDataJSON),
        authenticatorData: encode(credential.response.authenticatorData),
        signature: encode(credential.response.signature),
        userHandle: credential.response.userHandle ? encode(credential.response.userHandle) : null
      }
    };
    const receipt = await responseJson(await fetch("/complete", {
      method: "POST", headers: {"Content-Type": "application/json"}, body: JSON.stringify(assertion)
    }));
    result.textContent = "Review signature retained. Reset and trading remain disabled. " + receipt.envelope_sha256;
  } catch (error) { result.textContent = error.message; }
});
