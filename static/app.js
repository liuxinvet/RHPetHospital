/* 仁合宠物医院管理系统 - 前端交互脚本 */

// 删除/敏感操作统一确认
function confirmSubmit(msg) {
  return window.confirm(msg || '确定执行该操作吗？');
}

// Flash 消息自动消失
document.addEventListener('DOMContentLoaded', function () {
  setTimeout(function () {
    document.querySelectorAll('.flash').forEach(function (el) {
      el.style.transition = 'opacity .4s';
      el.style.opacity = '0';
      setTimeout(function () { el.remove(); }, 400);
    });
  }, 3000);
});

// 处方明细：添加一行
function addPresRow(medicines) {
  var tbody = document.getElementById('pres-body');
  var tr = document.createElement('tr');
  var idx = tbody.rows.length;
  tr.innerHTML =
    '<td>' +
    '<select name="med_id[]" class="pres-med" style="min-width:180px" onchange="updatePresRow(this)">' +
    '<option value="">-- 选择药品 --</option>' +
    medicines.map(function (m) {
      return '<option value="' + m.id + '" data-price="' + m.sale_price + '" data-stock="' + m.stock + '">' + m.name + '（库存' + m.stock + '）</option>';
    }).join('') +
    '</select></td>' +
    '<td><input type="number" name="qty[]" value="1" min="1" style="width:70px" oninput="calcPresTotal()"></td>' +
    '<td><input type="text" name="dosage[]" style="min-width:140px" placeholder="用法用量，如：每日2次每次1片"></td>' +
    '<td class="pres-price">0.00</td>' +
    '<td class="pres-sub">0.00</td>' +
    '<td><button type="button" class="btn btn-danger btn-xs" onclick="this.closest(\'tr\').remove();calcPresTotal()">删</button></td>';
  tbody.appendChild(tr);
  calcPresTotal();
}

function updatePresRow(sel) {
  var tr = sel.closest('tr');
  var opt = sel.options[sel.selectedIndex];
  var price = opt.getAttribute('data-price') || 0;
  tr.querySelector('.pres-price').textContent = parseFloat(price).toFixed(2);
  calcPresTotal();
}

function calcPresTotal() {
  var tbody = document.getElementById('pres-body');
  if (!tbody) return;
  var total = 0;
  Array.prototype.forEach.call(tbody.rows, function (tr) {
    var med = tr.querySelector('.pres-med');
    var qty = tr.querySelector('input[name="qty[]"]');
    if (!med || !med.value) { tr.querySelector('.pres-sub').textContent = '0.00'; return; }
    var price = parseFloat(med.options[med.selectedIndex].getAttribute('data-price') || 0);
    var q = parseInt(qty.value || 0);
    var sub = price * q;
    tr.querySelector('.pres-sub').textContent = sub.toFixed(2);
    total += sub;
  });
  var el = document.getElementById('pres-total');
  if (el) el.textContent = total.toFixed(2);
}

// 收费明细：添加一行
function addBillRow() {
  var tbody = document.getElementById('bill-body');
  var tr = document.createElement('tr');
  tr.innerHTML =
    '<td><select name="item_type[]" style="width:110px">' +
    '<option>挂号费</option><option>诊疗费</option><option>药品费</option>' +
    '<option>检查费</option><option>住院费</option><option>寄养费</option><option>美容费</option><option>其他</option>' +
    '</select></td>' +
    '<td><input type="text" name="item_name[]" placeholder="项目名称" style="min-width:160px"></td>' +
    '<td><input type="number" name="qty[]" value="1" min="1" style="width:70px" oninput="calcBillTotal()"></td>' +
    '<td><input type="number" name="price[]" value="0" min="0" step="0.01" style="width:90px" oninput="calcBillTotal()"></td>' +
    '<td><input type="number" name="member_price[]" value="" min="0" step="0.01" style="width:90px" placeholder="可选" oninput="calcBillTotal()">' +
    '<label class="chk"><input type="checkbox" name="is_member_price[]" value="1" onchange="applyMemberPrice(this)"> 按会员价</label></td>' +
    '<td class="bill-sub">0.00</td>' +
    '<td><button type="button" class="btn btn-danger btn-xs" onclick="this.closest(\'tr\').remove();calcBillTotal()">删</button></td>';
  tbody.appendChild(tr);
  calcBillTotal();
}

function applyMemberPrice(chk) {
  // 勾选会员价：若填写了会员价则小计按会员价计
  calcBillTotal();
}

function calcBillTotal() {
  var tbody = document.getElementById('bill-body');
  if (!tbody) return;
  var total = 0;
  Array.prototype.forEach.call(tbody.rows, function (tr) {
    var price = parseFloat(tr.querySelector('input[name="price[]"]').value || 0);
    var mp = parseFloat(tr.querySelector('input[name="member_price[]"]').value || 0);
    var chk = tr.querySelector('input[name="is_member_price[]"]');
    var useMember = chk && chk.checked && mp > 0;
    if (useMember) price = mp;
    var q = parseInt(tr.querySelector('input[name="qty[]"]').value || 0);
    var sub = price * q;
    tr.querySelector('.bill-sub').textContent = sub.toFixed(2);
    total += sub;
  });
  var el = document.getElementById('bill-total');
  if (el) el.textContent = total.toFixed(2);
  var paid = document.getElementById('paid-input');
  if (paid) paid.value = total.toFixed(2);
}

// 收费：从处方带入
function loadPrescription(presId, urlBase) {
  if (!presId) return;
  fetch(urlBase + presId)
    .then(function (r) { return r.json(); })
    .then(function (data) {
      if (!data.ok) { alert(data.msg || '加载失败'); return; }
      document.getElementById('pet_id').value = data.pet_id;
      document.getElementById('owner_id').value = data.owner_id;
      var ownerText = document.getElementById('owner-text');
      if (ownerText) ownerText.textContent = data.owner_name;
      var tbody = document.getElementById('bill-body');
      tbody.innerHTML = '';
      data.items.forEach(function (it) {
        var tr = document.createElement('tr');
        tr.innerHTML =
          '<td><select name="item_type[]" style="width:110px">' +
          '<option>药品费</option><option>挂号费</option><option>诊疗费</option><option>检查费</option>' +
          '<option>住院费</option><option>寄养费</option><option>美容费</option><option>其他</option>' +
          '</select></td>' +
          '<td><input type="text" name="item_name[]" value="' + it.name + '" style="min-width:160px"></td>' +
          '<td><input type="number" name="qty[]" value="' + it.qty + '" min="1" style="width:70px" oninput="calcBillTotal()"></td>' +
          '<td><input type="number" name="price[]" value="' + it.price + '" min="0" step="0.01" style="width:90px" oninput="calcBillTotal()"></td>' +
          '<td><input type="number" name="member_price[]" value="" min="0" step="0.01" style="width:90px" placeholder="可选" oninput="calcBillTotal()">' +
          '<label class="chk"><input type="checkbox" name="is_member_price[]" value="1" onchange="applyMemberPrice(this)"> 按会员价</label></td>' +
          '<td class="bill-sub">' + it.subtotal.toFixed(2) + '</td>' +
          '<td><button type="button" class="btn btn-danger btn-xs" onclick="this.closest(\'tr\').remove();calcBillTotal()">删</button></td>';
        tbody.appendChild(tr);
      });
      calcBillTotal();
    })
    .catch(function () { alert('加载处方失败'); });
}
