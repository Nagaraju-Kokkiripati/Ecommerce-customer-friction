'use strict';
let user = null, catalog = [], cart = {items: [], total: 0};
const compared = new Set();
const $ = id => document.getElementById(id);
const money = value => new Intl.NumberFormat('en-IN', {style:'currency',currency:'INR',maximumFractionDigits:0}).format(value);
const esc = value => String(value).replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
async function api(path, options={}) {
  const response = await fetch('/api/shop'+path, {headers:{'Content-Type':'application/json'},...options});
  const data = await response.json();
  if (!response.ok) throw new Error(typeof data.detail === 'string' ? data.detail : 'Check the form and try again.');
  return data;
}
let noticeTimer;
function notify(message) { $('notice').textContent=message; $('notice').hidden=false; clearTimeout(noticeTimer); noticeTimer=setTimeout(()=>$('notice').hidden=true,6000); }
function reveal(id) { $(id).hidden=false; $(id).scrollIntoView({behavior:'smooth',block:'start'}); }
function requireAccount() { if(user)return true; reveal('account'); notify('Sign in or create an account to shop.'); return false; }
async function track(type, details={}) { if(user) await api('/events',{method:'POST',body:JSON.stringify({type,...details})}); }

// Original SVG product illustrations, bundled with the application.
function art(product) {
  const shapes = {
    headphones:'<path d="M75 145v-35a65 65 0 0 1 130 0v35" fill="none" stroke="#34473f" stroke-width="15"/><rect x="58" y="119" width="35" height="69" rx="17" fill="#34473f"/><rect x="187" y="119" width="35" height="69" rx="17" fill="#34473f"/>',
    backpack:'<path d="M117 61v-8a23 23 0 0 1 46 0v8" fill="none" stroke="#465c48" stroke-width="9"/><rect x="79" y="63" width="122" height="143" rx="33" fill="#526c54"/><rect x="96" y="132" width="88" height="53" rx="13" fill="#789278"/><path d="M108 141h65" stroke="#d5d6bb" stroke-width="4"/>',
    lamp:'<path d="M91 207h106M146 206V122l39-49" fill="none" stroke="#514944" stroke-width="12" stroke-linecap="round"/><path d="M142 68q38-28 70 0l-7 41h-72z" fill="#d79049"/><ellipse cx="169" cy="110" rx="36" ry="7" fill="#ffd59b"/>',
    mug:'<path d="M188 98h18q35 0 24 39-8 24-42 19" fill="none" stroke="#ae806e" stroke-width="15"/><path d="M77 88h113v86q0 31-56 31t-57-31z" fill="#bf9685"/><ellipse cx="134" cy="89" rx="57" ry="12" fill="#e6c6ae"/><ellipse cx="134" cy="89" rx="47" ry="7" fill="#6b4f43"/>',
    shoe:'<path d="M58 160l26-69 59 7 26 34 57 15q21 7 15 39H58z" fill="#f9f7ef" stroke="#556b68" stroke-width="3"/><path d="M58 182h184v18H55z" fill="#a5b4a5"/><path d="M122 115l34 1m-29 11l39 1m-29 11l38 1" stroke="#556b68" stroke-width="5"/>',
    book:'<rect x="83" y="42" width="120" height="170" rx="9" fill="#416253"/><path d="M95 43v167" stroke="#233f32" stroke-width="4"/><path d="M117 89h57m-57 12h39" stroke="#b6bba2" stroke-width="3"/><path d="M176 167v55l-10-9-10 9v-55" fill="#dda975"/>',
  };
  return `<svg viewBox="0 0 280 250" role="img" aria-label="${esc(product.name)} illustration"><ellipse cx="140" cy="222" rx="86" ry="9" fill="#0000000b"/>${shapes[product.art]}</svg>`;
}
function renderCatalog() {
  const query=$('search').value.trim().toLowerCase(), category=$('category').value;
  const items=catalog.filter(p=>(!category||p.category===category)&&`${p.name} ${p.description}`.toLowerCase().includes(query));
  $('product-count').textContent=`${items.length} essentials`;
  $('products').innerHTML=items.map(p=>`<article class="product"><button class="product-art" data-view="${p.id}" style="background:${p.color}" aria-label="View ${esc(p.name)}">${art(p)}</button><h3>${esc(p.name)}</h3><p>${esc(p.category)} · Free delivery</p><p class="price">${money(p.price)}</p><div class="product-actions"><button class="primary" data-add="${p.id}">Add to bag</button><button data-compare="${p.id}">${compared.has(p.id)?'Remove comparison':'Compare'}</button></div></article>`).join('')||'<p>No products found. Try another search or category.</p>';
  return items.length;
}
async function loadCart() { if(!user)return; cart=await api('/cart'); renderCart(); }
function renderCart() {
  $('cart-count').textContent=cart.items.reduce((total,p)=>total+p.quantity,0);
  $('cart-items').innerHTML=cart.items.map(p=>`<div class="cart-row"><div><strong>${esc(p.name)}</strong><p>${money(p.price)} each</p></div><label>Quantity<input type="number" min="1" max="20" value="${p.quantity}" data-quantity="${p.id}" aria-label="${esc(p.name)} quantity"></label><button data-remove="${p.id}">Remove</button></div>`).join('')||'<p>Your bag is empty. Find something you love in the collection.</p>';
  $('cart-total').textContent=`Total ${money(cart.total)} · Delivery included`;
  $('checkout-button').disabled=!cart.items.length;
}
async function updateCart(id,quantity) { cart=await api('/cart',{method:'PUT',body:JSON.stringify({product_id:id,quantity})});renderCart(); }
async function loadOrders() {
  const orders=await api('/orders');
  $('orders-section').hidden=false;
  $('orders').innerHTML=orders.map(o=>`<div class="cart-row"><div><strong>${esc(o.id)}</strong><p>${new Date(o.created).toLocaleString()} · ${esc(o.status)}</p><p>${o.items.map(p=>`${esc(p.name)} × ${p.quantity}`).join(', ')}</p></div><strong>${money(o.total)}</strong></div>`).join('')||'<p>No orders yet.</p>';
}
async function accountChanged() {
  $('account-button').textContent=user?user.name:'Sign in';$('auth-forms').hidden=!!user;$('logout-button').hidden=!user;
  $('session-label').textContent=user?`Tracking session: ${user.session_id}`:'Sign in to save your bag and start a tracked shopping session.';
  if(user){await loadCart();await loadOrders();}else{cart={items:[],total:0};renderCart();$('orders-section').hidden=true;$('checkout').hidden=true;$('bag').hidden=true;}
}
function safe(handler) {return async event=>{try{await handler(event);}catch(error){notify(error.message);}};}
['login','signup'].forEach(kind=>$(kind+'-form').addEventListener('submit',safe(async event=>{
  event.preventDefault();const form=event.currentTarget;const button=form.querySelector('button');button.disabled=true;
  try{const data=Object.fromEntries(new FormData(form));if(kind==='signup')data.consent=form.elements.consent.checked;
    user=await api('/'+kind,{method:'POST',body:JSON.stringify(data)});form.reset();await accountChanged();notify('You’re signed in. Your shopping journey is now being recorded.');
  }finally{button.disabled=false;}
})));
$('account-button').onclick=()=>reveal('account');
$('logout-button').onclick=safe(async()=>{await api('/logout',{method:'POST'});user=null;await accountChanged();notify('Signed out.');});
$('cart-button').onclick=safe(async()=>{if(requireAccount()){await loadCart();reveal('bag');}});
$('products').addEventListener('click',safe(async event=>{
  const button=event.target.closest('button');if(!button)return;
  if(button.dataset.view){const p=catalog.find(p=>p.id===button.dataset.view);await track('product_view',{product_id:p.id});$('product-detail').innerHTML=`${art(p)}<h2>${esc(p.name)}</h2><p>${esc(p.description)}</p><p>${money(p.price)} · Delivery in 3–5 business days</p>`;$('product-dialog').showModal();}
  if(button.dataset.add&&requireAccount()){const id=button.dataset.add;await updateCart(id,(cart.items.find(p=>p.id===id)?.quantity||0)+1);notify('Added to your bag.');}
  if(button.dataset.compare){const id=button.dataset.compare;if(compared.has(id))compared.delete(id);else{if(compared.size===3)throw new Error('Compare up to three products.');compared.add(id);await track('product_compare',{product_id:id});}renderCatalog();$('comparison').hidden=!compared.size;$('comparison-items').innerHTML=catalog.filter(p=>compared.has(p.id)).map(p=>`<p><strong>${esc(p.name)} · ${money(p.price)}</strong><br>${esc(p.description)}</p>`).join('');}
}));
$('close-product').onclick=()=>$('product-dialog').close();
$('search-form').addEventListener('submit',safe(async event=>{event.preventDefault();const count=renderCatalog();await track('search',{query:$('search').value});if(!count)await track('search_no_results',{query:$('search').value});}));
$('category').onchange=renderCatalog;
$('cart-items').addEventListener('click',safe(async event=>{if(event.target.dataset.remove)await updateCart(event.target.dataset.remove,0);}));
$('cart-items').addEventListener('change',safe(async event=>{if(event.target.dataset.quantity)await updateCart(event.target.dataset.quantity,Number(event.target.value));}));
$('checkout-button').onclick=safe(async()=>{if(!requireAccount())return;await loadCart();if(!cart.items.length)return;await track('checkout_start');reveal('checkout');});
$('payment-form').addEventListener('submit',safe(async event=>{
  event.preventDefault();const button=event.currentTarget.querySelector('button');button.disabled=true;
  try{const result=await api('/payment',{method:'POST',body:JSON.stringify({outcome:$('outcome').value,delivery_address:$('address').value,method:$('method').value})});
    if(result.outcome==='success'){notify(`Demo order ${result.order_id} confirmed.`);$('checkout').hidden=true;await loadCart();await loadOrders();reveal('orders-section');}
    else notify(result.outcome==='failure'?'Simulated payment failed. Your bag is saved; try the demo wallet or retry.':'Payment cancelled. Your bag is saved.');
  }finally{button.disabled=false;}
}));
(async()=>{try{catalog=await api('/products');$('hero-art').innerHTML=art(catalog[1]);renderCatalog();try{user=await api('/me');}catch{user=null;}await accountChanged();}catch(error){notify(error.message);}})();
