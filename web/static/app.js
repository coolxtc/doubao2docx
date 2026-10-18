/* 豆包导出 H5 前端逻辑：原生 JS，无框架、无构建步骤 */

(function () {
  'use strict';

  // 后端 src/scraper/steps.py 的 STEP_COUNT：步骤 0-5 为具名步骤，终态被归一为 6
  const STEP_COUNT = 6;

  // 与后端 src/cli.py 的 _get_url_tag 一致，保证卡片短标签和日志对得上
  const THREAD_RE = /\/thread\/([A-Za-z0-9]+)/;

  // 刷新页面后凭此续接 SSE（SSE 服务端会回放历史，前端不需要自己缓存事件）
  const STORE_KEY = 'doubao-export-current-task';

  // 提示区最多保留的条数，防止长时间批量导出刷满屏幕
  const MAX_ALERTS = 6;

  // 后端 /api/download-zip 的硬上限，超出会被 422 拒绝，这里在点击前就拦住
  const ZIP_MAX = 50;

  // 打包按钮加载态的恢复时长，理由见 downloadZip()
  const ZIP_BUSY_MS = 8000;

  const els = {
    health: document.getElementById('health'),
    healthText: document.getElementById('healthText'),
    urls: document.getElementById('urls'),
    urlCount: document.getElementById('urlCount'),
    level: document.getElementById('level'),
    concurrency: document.getElementById('concurrency'),
    submit: document.getElementById('submit'),
    clear: document.getElementById('clear'),
    alerts: document.getElementById('alerts'),
    summary: document.getElementById('summary'),
    list: document.getElementById('taskList'),
    empty: document.getElementById('empty'),
    bar: document.getElementById('selectionBar'),
    barCount: document.getElementById('selectionCount'),
    barHint: document.getElementById('selectionHint'),
    selectAll: document.getElementById('selectAll'),
    zipBtn: document.getElementById('downloadZip'),
    zipLink: document.getElementById('zipLink')
  };

  // 渲染模型：task_index -> { el, data }；同一索引只有一张卡片，收到新事件就整体替换
  const cards = new Map();

  // 勾选中的 task_index：卡片每帧都会整体重建 DOM，勾选状态只能存在 JS 里
  const selected = new Set();

  let currentTaskId = '';
  let currentUrls = [];
  let stream = null;
  let running = false;
  // zip 请求进行中（按钮加载态）与其恢复定时器
  let zipBusy = false;
  let zipTimer = 0;

  /**
   * 创建元素；文本一律走 textContent
   * 文件名、错误信息都来自服务端，用 textContent 才不会当 HTML 解析
   */
  function el(tag, className, text) {
    const node = document.createElement(tag);
    if (className) {
      node.className = className;
    }
    if (text !== undefined && text !== null) {
      node.textContent = String(text);
    }
    return node;
  }

  /** 提取链接短标签 */
  function urlTag(url, index) {
    const matched = THREAD_RE.exec(String(url || ''));
    if (matched) {
      return 'thread ' + matched[1];
    }
    const text = String(url || '');
    return text ? text.slice(0, 24) : '第 ' + index + ' 条链接';
  }

  /**
   * 按 "/" 分段编码相对路径
   *
   * download_path 形如 "260412/260412-1 项目方案讨论.docx"，同时含分隔符、空格和中文。
   * 必须切段后逐段 encodeURIComponent：整串 encode 会把目录分隔符变成 %2F，
   * 后端 /download/{file_path:path} 无法还原成多级路径，结果就是 404/403。
   */
  function encodePath(path) {
    return String(path)
      .split('/')
      .filter(function (segment) { return segment.length > 0; })
      .map(encodeURIComponent)
      .join('/');
  }

  /** 单文件下载 URL */
  function downloadUrl(path) {
    return '/download/' + encodePath(path);
  }

  /**
   * zip 下载 URL：每个路径重复一个 paths= 键
   *
   * 每个值复用 encodePath，让 "/" 留在 query 的结构层、只编码中文与空格。
   * 相对路径里不会出现 "&" 与 "="（文件名不允许），所以直接拼 query 是安全的。
   */
  function zipUrl(paths) {
    const query = paths.map(function (path) { return 'paths=' + encodePath(path); }).join('&');
    return '/api/download-zip' + (query ? '?' + query : '');
  }

  /** 取路径最后一段作为展示用文件名 */
  function baseName(path) {
    const segments = String(path).split('/').filter(function (segment) { return segment.length > 0; });
    return segments.length ? segments[segments.length - 1] : '';
  }

  /** 请求 JSON 并把后端的 detail 还原成可读错误 */
  function requestJson(url, options) {
    return fetch(url, options).then(function (response) {
      return response.text().then(function (text) {
        let payload = null;
        try {
          payload = text ? JSON.parse(text) : null;
        } catch (err) {
          payload = null;
        }
        if (!response.ok) {
          throw new Error(describeError(payload, text, response.status));
        }
        if (!payload || typeof payload !== 'object') {
          throw new Error('服务返回内容无法解析');
        }
        return payload;
      });
    });
  }

  /** 从错误响应体里取人类可读文案 */
  function describeError(payload, text, status) {
    const detail = payload && payload.detail;
    if (typeof detail === 'string' && detail) {
      return detail;
    }
    // FastAPI 参数校验失败时 detail 是数组，取其中的 msg 拼成一句
    if (Array.isArray(detail)) {
      const messages = detail.map(function (item) { return item && item.msg ? item.msg : ''; })
        .filter(function (item) { return item.length > 0; });
      if (messages.length) {
        return messages.join('；');
      }
    }
    return text ? text.slice(0, 200) : '请求失败（HTTP ' + status + '）';
  }

  /** 解析文本框：一行一个链接 */
  function parseUrls() {
    return String(els.urls.value || '')
      .split(/\r?\n/)
      .map(function (line) { return line.trim(); })
      .filter(function (line) { return line.length > 0; });
  }

  function refreshUrlCount() {
    const count = parseUrls().length;
    els.urlCount.textContent = count === 0
      ? '已识别 0 个链接'
      : '已识别 ' + count + ' 个链接';
  }

  /** 加一条提示（warning 事件与接口 detail 都走这里，不能只 console.log） */
  function addAlert(message, kind) {
    const box = el('div', 'alert alert-' + (kind || 'info'));
    const body = el('div', 'alert-body', message);
    const close = el('button', 'alert-close', '×');
    close.type = 'button';
    close.setAttribute('aria-label', '关闭提示');
    close.addEventListener('click', function () { box.remove(); });
    box.append(body, close);
    els.alerts.prepend(box);
    while (els.alerts.children.length > MAX_ALERTS) {
      els.alerts.lastElementChild.remove();
    }
  }

  function clearAlerts() {
    els.alerts.textContent = '';
  }

  /** 终态判定：后端终态文本固定为「导出完成」「导出失败」，step 归一为 STEP_COUNT */
  function isTerminal(data) {
    return Number(data.step) >= STEP_COUNT || /失败|错误|异常/.test(String(data.status || ''));
  }

  function isFailure(data) {
    return /失败|错误|异常/.test(String(data.status || ''));
  }

  function stateOf(data) {
    if (!data) {
      return 'pending';
    }
    if (!isTerminal(data)) {
      return 'running';
    }
    return isFailure(data) ? 'failed' : 'success';
  }

  const BADGE_TEXT = {
    pending: '排队中',
    running: '进行中',
    success: '完成',
    failed: '失败',
    interrupted: '未结束'
  };

  /** 卡片正文：序号 + 短标签 + 徽标 + 进度段 + 步骤名 + 耗时 + 结果 */
  function buildCard(index, data, state) {
    const frag = document.createDocumentFragment();

    const head = el('div', 'task-head');
    head.append(
      el('span', 'task-index', '#' + index),
      el('span', 'task-tag', urlTag(currentUrls[index - 1], index)),
      el('span', 'badge', BADGE_TEXT[state])
    );
    frag.append(head);

    // 后端 step 是「已完成的步骤数」，终态为 STEP_COUNT；进度段按同一语义渲染
    const filled = Math.max(0, Math.min(Number(data.step) || 0, STEP_COUNT));
    const bar = el('div', 'bar');
    const segments = [];
    for (let i = 0; i < STEP_COUNT; i += 1) {
      segments.push(el('i', 'bar-seg' + (i < filled ? ' bar-seg-done' : '')));
    }
    bar.append.apply(bar, segments);
    frag.append(bar);

    let stepText;
    if (state === 'pending') {
      stepText = '等待开始';
    } else if (state === 'interrupted') {
      stepText = '任务结束前没有收到该条进度';
    } else {
      stepText = (data.step_name || data.status || '处理中');
    }
    const elapsed = Number(data.elapsed) || 0;
    const rightText = filled + '/' + STEP_COUNT + (elapsed > 0 ? ' · ' + elapsed.toFixed(1) + ' 秒' : '');
    const line = el('div', 'task-line');
    line.append(
      el('span', 'task-step', stepText),
      el('span', 'task-elapsed', rightText)
    );
    frag.append(line);

    if (state === 'failed') {
      frag.append(el('p', 'task-detail', data.result || '导出失败，未返回原因'));
    } else if (state === 'success') {
      const filename = data.result || baseName(data.download_path || '');
      frag.append(el('p', 'task-file', filename || '导出完成'));
      const foot = el('div', 'task-foot');
      if (data.download_path) {
        // 勾选行用 label 包住复选框：整块 48px 高都是命中区，比裸复选框好点
        const pick = el('label', 'pick');
        const box = el('input', 'pick-input');
        box.type = 'checkbox';
        box.dataset.index = String(index);
        box.checked = selected.has(index);
        box.setAttribute('aria-label', '选入 zip：' + (filename || baseName(data.download_path)));
        pick.append(box, el('span', 'pick-text', '选入 zip'));
        const link = el('a', 'btn btn-download', '下载到手机');
        link.href = downloadUrl(data.download_path);
        foot.append(pick, link);
        frag.append(foot);
      } else {
        frag.append(el('p', 'task-detail', '未取到下载路径，请到 NAS 的 data/export 目录查看'));
      }
    } else if (state === 'interrupted') {
      frag.append(el('p', 'task-detail', '浏览器池不可用或任务被中断时会出现该状态'));
    }

    return frag;
  }

  /** 按 task_index 覆盖式渲染：同一索引可能收到多条事件（终态后还会补发带下载路径的一条） */
  function renderCard(index, data, forcedState) {
    let view = cards.get(index);
    if (!view) {
      view = { el: el('li'), data: null };
      cards.set(index, view);
      els.list.append(view.el);
    }
    view.data = data || {};
    const state = forcedState || stateOf(view.data);
    // 卡片不再是「成功且有下载路径」就撤销勾选资格，避免待打包列表里混进拿不到的条目
    if (state !== 'success' || !view.data.download_path) {
      selected.delete(index);
    }
    view.el.className = 'task-card task-state-' + state + (selected.has(index) ? ' is-picked' : '');
    view.el.textContent = '';
    view.el.append(buildCard(index, view.data, state));
    refreshSummary();
    refreshSelectionBar();
  }

  function refreshSummary() {
    if (!cards.size) {
      els.summary.textContent = running ? '任务已提交，等待进度…' : '等待开始';
      els.empty.hidden = cards.size > 0;
      return;
    }
    let success = 0;
    let failed = 0;
    let active = 0;
    cards.forEach(function (view) {
      const state = stateOf(view.data);
      if (state === 'success') { success += 1; } else if (state === 'failed') { failed += 1; } else { active += 1; }
    });
    els.summary.textContent = '共 ' + cards.size + ' · 成功 ' + success + ' · 失败 ' + failed + ' · 未结束 ' + active;
    els.empty.hidden = true;
  }

  /** 有勾选资格的卡片：导出成功且已拿到下载路径 */
  function selectableIndexes() {
    const list = [];
    cards.forEach(function (view, index) {
      if (stateOf(view.data) === 'success' && view.data.download_path) {
        list.push(index);
      }
    });
    return list.sort(function (a, b) { return a - b; });
  }

  /** 勾选变化后同步卡片外观：只改 class 与复选框，不重建整张卡 */
  function syncCheckboxes() {
    cards.forEach(function (view, index) {
      const picked = selected.has(index);
      view.el.classList.toggle('is-picked', picked);
      const box = view.el.querySelector('.pick-input');
      if (box) {
        box.checked = picked;
      }
    });
  }

  /** 全选实际应覆盖的条数：可选卡片再多也不会越过后端上限 */
  function fullPickCount(candidates) {
    return Math.min(candidates.length, ZIP_MAX);
  }

  /**
   * 刷新吸底操作条
   *
   * 条内文案会换行、高度不固定，实测高度写回 CSS 变量，正文底部留白才刚好让开它。
   */
  function refreshSelectionBar() {
    const candidates = selectableIndexes();
    const count = selected.size;
    const overLimit = count > ZIP_MAX;
    els.bar.hidden = candidates.length === 0;
    document.body.classList.toggle('has-selection', !els.bar.hidden);
    document.documentElement.style.setProperty('--selection-bar-h', (els.bar.hidden ? 0 : els.bar.offsetHeight) + 'px');
    els.barCount.textContent = '已选 ' + count + ' 个';
    els.barHint.textContent = overLimit
      ? '一次最多打包 ' + ZIP_MAX + ' 个，请取消部分勾选'
      : '将打包为 1 个 zip，包含选中的 Word 文档';
    els.selectAll.textContent = (count > 0 && count === fullPickCount(candidates)) ? '取消全选' : '全选';
    els.zipBtn.disabled = zipBusy || count === 0 || overLimit;
  }

  function toggleSelectAll() {
    const candidates = selectableIndexes();
    if (!candidates.length) { return; }
    if (selected.size === fullPickCount(candidates)) {
      selected.clear();
    } else {
      // 全选也不越过后端上限
      candidates.slice(0, ZIP_MAX).forEach(function (index) { selected.add(index); });
      if (candidates.length > ZIP_MAX) {
        addAlert('可打包的文档有 ' + candidates.length + ' 个，一次最多 ' + ZIP_MAX + ' 个，已自动取前 ' + ZIP_MAX + ' 个', 'warn');
      }
    }
    syncCheckboxes();
    refreshSelectionBar();
  }

  /** 复选框变更走列表事件委托：卡片每帧重建 DOM，逐个绑定会随节点一起丢掉 */
  function onPickChange(event) {
    const box = event.target;
    if (!box || !box.classList || !box.classList.contains('pick-input')) { return; }
    const index = Number(box.dataset.index);
    const view = cards.get(index);
    if (!view || stateOf(view.data) !== 'success' || !view.data.download_path) {
      box.checked = false;
      return;
    }
    if (box.checked) {
      if (selected.size >= ZIP_MAX) {
        addAlert('一次最多打包 ' + ZIP_MAX + ' 个文件，请先取消部分勾选', 'warn');
        box.checked = false;
        return;
      }
      selected.add(index);
    } else {
      selected.delete(index);
    }
    syncCheckboxes();
    refreshSelectionBar();
  }

  function setZipBusy(value) {
    zipBusy = value;
    els.zipBtn.textContent = value ? '打包中…' : '下载 zip';
    if (value) {
      zipTimer = window.setTimeout(function () { setZipBusy(false); }, ZIP_BUSY_MS);
    } else if (zipTimer) {
      window.clearTimeout(zipTimer);
      zipTimer = 0;
    }
    refreshSelectionBar();
  }

  /**
   * 打包下载勾选的文档
   *
   * 走 GET 导航（点隐藏锚点）而不是 fetch + blob：iOS Safari 对 blob 配合 download
   * 属性的下载支持不可靠，交给浏览器按响应的 content-disposition 原生落地才稳。
   * 代价是浏览器接管了这次跳转，前端无法感知打包与传输何时结束，
   * 所以只能用 ZIP_BUSY_MS 固定超时把按钮恢复——它不代表下载已完成。
   */
  function downloadZip() {
    if (zipBusy) { return; }
    const indexes = selectableIndexes().filter(function (index) { return selected.has(index); });
    if (!indexes.length) {
      addAlert('请先在卡片上勾选要打包的文档', 'warn');
      refreshSelectionBar();
      return;
    }
    const paths = [];  // 待打包的相对路径
    const missing = [];  // 已勾选但拿不到路径的卡片序号
    indexes.forEach(function (index) {
      const path = cards.get(index).data.download_path;
      if (path) {
        paths.push(String(path));
      } else {
        missing.push(index);
      }
    });
    // 点击前就拦下缺路径的项：后端 403/404/422 会让浏览器跳到错误页，用户只会以为页面坏了
    if (missing.length) {
      addAlert('第 ' + missing.join('、') + ' 条没取到下载路径，请取消勾选或重新导出', 'error');
      return;
    }
    if (paths.length > ZIP_MAX) {
      addAlert('一次最多打包 ' + ZIP_MAX + ' 个文件，请减少勾选', 'warn');
      return;
    }
    els.zipLink.href = zipUrl(paths);
    setZipBusy(true);
    els.zipLink.click();
    addAlert('已请求打包 ' + paths.length + ' 个文档，浏览器会开始下载 zip（现场打包可能要几秒）', 'info');
  }

  function renderPendingCards(urls) {
    urls.forEach(function (_url, position) {
      renderCard(position + 1, { step: 0, status: '排队中' }, 'pending');
    });
  }

  function resetProgress() {
    closeStream();
    cards.clear();
    els.list.textContent = '';
    // 新一批任务与旧批次无关，勾选与打包按钮状态一并归零
    selected.clear();
    setZipBusy(false);
    refreshSelectionBar();
    currentTaskId = '';
    currentUrls = [];
  }

  function setRunning(value) {
    running = value;
    els.submit.disabled = value;
    els.clear.disabled = value;
    els.submit.textContent = value ? '导出中，请勿重复提交' : '开始导出';
    refreshSummary();
  }

  function saveTask() {
    try {
      sessionStorage.setItem(STORE_KEY, JSON.stringify({ taskId: currentTaskId, urls: currentUrls }));
    } catch (err) {
      // 隐私模式下 sessionStorage 可能抛错，续接功能降级即可，不影响导出
    }
  }

  function clearStoredTask() {
    try {
      sessionStorage.removeItem(STORE_KEY);
    } catch (err) {
      // 同上，忽略
    }
  }

  /**
   * 流结束后用 REST 快照兜底补齐下载路径
   *
   * SSE 历史缓冲有上限，长批次可能回放不到最早那条补发事件；
   * 快照只补 SSE 没给出的信息，已渲染为成功的卡片不降级。
   */
  function reconcile(taskId) {
    return requestJson('/api/export/' + encodeURIComponent(taskId), { method: 'GET' })
      .then(function (snapshot) {
        const results = Array.isArray(snapshot.results) ? snapshot.results : [];
        results.forEach(function (item) {
          const index = Number(item.task_index);
          if (!index || index < 1) { return; }
          const view = cards.get(index);
          if (view && stateOf(view.data) === 'success' && view.data.download_path) { return; }
          const previous = view ? view.data : {};
          renderCard(index, {
            step: STEP_COUNT,
            status: item.success ? '导出完成' : '导出失败',
            result: item.success ? (item.filename || '') : (item.error || previous.result || ''),
            download_path: item.download_path || previous.download_path || '',
            elapsed: Number(previous.elapsed) || 0
          });
        });
      })
      .catch(function (err) {
        addAlert('最终结果核对失败：' + err.message, 'warn');
      });
  }

  /** 流已结束但卡片仍停在中间态：说明后端根本没为这条推送进度（典型是浏览器池起不来） */
  function markUnfinished() {
    cards.forEach(function (view, index) {
      if (stateOf(view.data) === 'running' || stateOf(view.data) === 'pending') {
        renderCard(index, view.data, 'interrupted');
      }
    });
  }

  function closeStream() {
    if (stream) {
      stream.close();
      stream = null;
    }
  }

  function handleFrame(event) {
    if (event.type === 'task_update') {
      const index = Number(event.task_index);
      if (index >= 1) {
        renderCard(index, event);
      }
      return;
    }
    if (event.type === 'warning') {
      addAlert(event.message || '服务端警告（无内容）', 'warn');
      return;
    }
    if (event.type === 'done') {
      // 必须主动 close：否则 EventSource 会无限重连已完成的流
      closeStream();
      clearStoredTask();
      setRunning(false);
      reconcile(currentTaskId).then(markUnfinished, markUnfinished);
      addAlert('本批导出已结束，成功的条目可单条下载，也可勾选后点底部「下载 zip」', 'info');
      return;
    }
    // task_add 等其它事件类型批量路径不会产生，无需处理
  }

  function openStream(taskId) {
    closeStream();
    const source = new EventSource('/api/export/' + encodeURIComponent(taskId) + '/stream');
    source.onmessage = function (message) {
      let event = null;
      try {
        event = JSON.parse(message.data);
      } catch (err) {
        addAlert('进度数据解析失败：' + String(message.data).slice(0, 120), 'warn');
        return;
      }
      handleFrame(event);
    };
    source.onerror = function () {
      // readyState CONNECTING 说明浏览器正在自动重连（切后台/锁屏掐断后属正常），不打扰用户
      if (source.readyState === EventSource.CLOSED) {
        closeStream();
        setRunning(false);
        markUnfinished();
        addAlert('与服务端的进度连接已断开，可下拉刷新页面重试', 'error');
      }
    };
    stream = source;
  }

  function submit() {
    if (running) { return; }
    const urls = parseUrls();
    if (!urls.length) {
      addAlert('请先粘贴至少一个豆包链接（一行一个）', 'warn');
      return;
    }
    const bad = urls.filter(function (url) { return !/^https?:\/\/\S+$/i.test(url); });
    if (bad.length) {
      addAlert('这些行不是 http(s) 链接，请检查：' + bad.slice(0, 2).join('、'), 'error');
      return;
    }
    // 并发数越界会被后端 422 拒绝，这里直接夹到合法区间
    const raw = parseInt(els.concurrency.value, 10);
    const concurrency = Number.isNaN(raw) ? 3 : Math.max(1, Math.min(10, raw));
    els.concurrency.value = String(concurrency);

    clearAlerts();
    resetProgress();
    currentUrls = urls;
    renderPendingCards(urls);
    setRunning(true);

    requestJson('/api/export', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ urls: urls, level: els.level.value, concurrency: concurrency })
    }).then(function (data) {
      if (!data.task_id) {
        throw new Error('服务未返回 task_id');
      }
      currentTaskId = data.task_id;
      saveTask();
      openStream(currentTaskId);
    }).catch(function (err) {
      setRunning(false);
      markUnfinished();
      addAlert('提交失败：' + err.message, 'error');
    });
  }

  function clearAll() {
    els.urls.value = '';
    refreshUrlCount();
    clearAlerts();
    if (!running) {
      resetProgress();
      refreshSummary();
    }
  }

  /** 读 /health：后端不启动浏览器，只核对二进制与目录，按具体缺失项给出可执行的提示 */
  function checkHealth() {
    els.health.dataset.state = 'checking';
    els.healthText.textContent = '检查服务状态…';
    requestJson('/health', { method: 'GET' }).then(function (data) {
      if (data.status === 'ok') {
        els.health.dataset.state = 'ok';
        // pandoc 缺失只影响公式排版质量，提示但不算故障
        els.healthText.textContent = data.pandoc === 'missing'
          ? '服务正常（未装 pandoc，公式会退化为纯文本）'
          : '服务正常';
      } else {
        els.health.dataset.state = 'degraded';
        els.healthText.textContent = data.browser_binary === 'missing'
          ? '浏览器未就位，导出会失败'
          : '导出目录不可写，请检查挂载配置';
      }
    }).catch(function () {
      els.health.dataset.state = 'offline';
      els.healthText.textContent = '无法连接服务，请检查地址与端口';
    });
  }

  function restoreTask() {
    let raw = null;
    try {
      raw = sessionStorage.getItem(STORE_KEY);
    } catch (err) {
      return;
    }
    if (!raw) { return; }
    let saved = null;
    try {
      saved = JSON.parse(raw);
    } catch (err) {
      clearStoredTask();
      return;
    }
    // 手机浏览器后台被回收会重载页面；凭 task_id 重新订阅，历史回放即可还原进度视图
    if (saved && typeof saved.taskId === 'string' && saved.taskId && Array.isArray(saved.urls) && saved.urls.length) {
      currentTaskId = saved.taskId;
      currentUrls = saved.urls;
      renderPendingCards(saved.urls);
      setRunning(true);
      openStream(currentTaskId);
      return;
    }
    clearStoredTask();
  }

  els.submit.addEventListener('click', submit);
  els.clear.addEventListener('click', clearAll);
  els.health.addEventListener('click', checkHealth);
  els.urls.addEventListener('input', refreshUrlCount);
  els.selectAll.addEventListener('click', toggleSelectAll);
  els.zipBtn.addEventListener('click', downloadZip);
  els.list.addEventListener('change', onPickChange);

  refreshUrlCount();
  refreshSummary();
  refreshSelectionBar();
  checkHealth();
  restoreTask();
})();
