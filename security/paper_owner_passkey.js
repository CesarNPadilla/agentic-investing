const decode = value => Uint8Array.from(atob(value.replace(/-/g, '+').replace(/_/g, '/')), c => c.charCodeAt(0));
const encode = value => btoa(String.fromCharCode(...new Uint8Array(value))).replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/, '');
let reviewDigest = null;
async function operate(mode) {
  const result = document.getElementById('result');
  result.textContent = 'Waiting for your passkey…';
  try {
    if (mode === 'review' && (!reviewDigest || !document.getElementById('review-consent').checked))
      throw new Error('Review the plan and check the approval box first.');
    const begin = await fetch(`/begin/${mode}`, {method: 'POST',
      headers: mode === 'review' ? {'X-Owner-Review-Sha256': reviewDigest} : {}});
    if (!begin.ok) throw new Error('Cannot begin. Enrollment may already exist, or verification needs enrollment.');
    const options = (await begin.json()).publicKey;
    options.challenge = decode(options.challenge);
    if (options.user) options.user.id = decode(options.user.id);
    for (const field of ['allowCredentials', 'excludeCredentials'])
      if (options[field]) options[field].forEach(item => item.id = decode(item.id));
    const credential = mode === 'enroll'
      ? await navigator.credentials.create({publicKey: options})
      : await navigator.credentials.get({publicKey: options});
    const body = {id: credential.id, rawId: encode(credential.rawId), type: credential.type,
      clientExtensionResults: credential.getClientExtensionResults(), response: {
        clientDataJSON: encode(credential.response.clientDataJSON)}};
    if (mode === 'enroll') body.response.attestationObject = encode(credential.response.attestationObject);
    else Object.assign(body.response, {authenticatorData: encode(credential.response.authenticatorData),
      signature: encode(credential.response.signature),
      userHandle: credential.response.userHandle ? encode(credential.response.userHandle) : null});
    const complete = await fetch(`/complete/${mode}`, {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(body)});
    if (!complete.ok) throw new Error('Verification rejected. No reset or trading action occurred.');
    result.textContent = mode === 'review'
      ? 'Recovery plan decision signed and saved. No journal, latch or trading permission changed.'
      : 'Passkey verified for this test. Latches and trading permissions remain unchanged.';
  } catch (error) { result.textContent = error.message || 'Passkey operation canceled or failed.'; }
}
document.getElementById('enroll').onclick = () => operate('enroll');
document.getElementById('verify').onclick = () => operate('verify');
document.getElementById('review').onclick = () => operate('review');
fetch('/recovery-review').then(async response => {
  if (!response.ok) throw new Error('No current recovery plan is available.');
  const data = await response.json();
  reviewDigest = data.digest;
  document.getElementById('review-summary').textContent =
    `${data.review.failed_check_count} failed check(s). Plan digest: ${data.digest}. Expires: ${data.review.expires_at_utc}.`;
  document.getElementById('review').disabled = false;
}).catch(error => document.getElementById('review-summary').textContent = error.message);
