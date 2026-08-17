// Admin AI Command Center JavaScript Client

async function executeAICommand(e) {
  e.preventDefault();
  const cmdInput = document.getElementById('ai-cmd-input');
  const docInput = document.getElementById('ai-doc-input');
  const btn = document.getElementById('ai-cmd-btn');
  const resultBox = document.getElementById('ai-cmd-result');
  const errorBox = document.getElementById('ai-cmd-error');

  if (!cmdInput || !cmdInput.value.trim()) return;

  if (resultBox) resultBox.classList.add('hidden');
  if (errorBox) errorBox.classList.add('hidden');

  if (btn) {
    btn.disabled = true;
    btn.innerHTML = '<i data-lucide="loader-2" class="w-4 h-4 animate-spin"></i> Executing AI Directive...';
    if (window.lucide) lucide.createIcons();
  }

  try {
    const res = await apiFetch('/ai-commands/execute', {
      method: 'POST',
      body: JSON.stringify({
        command: cmdInput.value.trim(),
        document_name: docInput ? docInput.value.trim() : undefined
      })
    });

    const data = await res.json();
    if (!res.ok) {
      if (errorBox) {
        errorBox.innerText = data.detail || 'Failed to execute AI command';
        errorBox.classList.remove('hidden');
      }
      return;
    }

    if (resultBox) {
      resultBox.innerText = data.message || 'AI Command executed successfully!';
      resultBox.classList.remove('hidden');
    }

    cmdInput.value = '';
    if (docInput) docInput.value = '';
  } catch (err) {
    if (errorBox) {
      errorBox.innerText = 'Server error processing AI directive';
      errorBox.classList.remove('hidden');
    }
  } finally {
    if (btn) {
      btn.disabled = false;
      btn.innerHTML = '<i data-lucide="sparkles" class="w-4 h-4"></i> Execute AI Command';
      if (window.lucide) lucide.createIcons();
    }
  }
}
