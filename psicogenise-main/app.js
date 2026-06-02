/*
 * Tela do aluno: mostra as 5 respostas na mesma tela, com som, figura
 * e preenchimento na ordem. O envio acontece apenas ao finalizar.
 */

(function () {
	const API_BASE_URL = typeof window.__API_BASE_URL === 'string'
		? window.__API_BASE_URL
		: (/^https?:$/.test(window.location.protocol) ? window.location.origin : '');
	const STUDENT = window.__STUDENT || {};
	const MESSAGE_ENDPOINT = '/api/messages';
	const CLOUD_ENDPOINT = '/api/cloud-inputs';
	const SOUND_ENDPOINT = '/api/sound';

	const QUESTIONS = [
		{ id: 'word-1', text: 'sol', visual: '☀️', source: 'cloud', label: 'Palavra 1', audio: 'audio/sol.ogg' },
		{ id: 'word-2', text: 'gato', visual: '🐈', source: 'cloud', label: 'Palavra 2', audio: 'audio/gato.ogg' },
		{ id: 'word-3', text: 'banana', visual: '🍌', source: 'cloud', label: 'Palavra 3', audio: 'audio/banana.ogg' },
		{ id: 'word-4', text: 'elefante', visual: '🐘', source: 'cloud', label: 'Palavra 4', audio: 'audio/elefante.ogg' },
		{ id: 'phrase-5', text: 'o gato faz miau', visual: '🐈 💬', source: 'main', label: 'Frase 5', audio: 'audio/frase-gato-miau.ogg' },
	];

	let soundRequestCounter = 0;
	let submitTokenCounter = 0;
	let finishing = false;

	const layer = document.getElementById('cloud-layer');
	const card = document.querySelector('.card');
	if (!card) return;
	if (layer) layer.innerHTML = '';

	function buildEndpoint(path) {
		return String(API_BASE_URL || '') + path;
	}

	function renderStudentPanel() {
		if (!STUDENT.nome) return;

		const panel = document.createElement('section');
		panel.className = 'student-panel';
		panel.setAttribute('aria-label', 'Aluno em teste');

		const name = document.createElement('strong');
		name.textContent = STUDENT.nome;

		const details = document.createElement('span');
		details.textContent = 'Serie: ' + STUDENT.serie + ' | Matricula: ' + STUDENT.matricula;

		panel.append(name, details);
		document.body.appendChild(panel);
	}

	function speakWord(word) {
		if (!word || !window.speechSynthesis) return false;

		window.speechSynthesis.cancel();
		const utterance = new SpeechSynthesisUtterance(word);
		utterance.lang = 'pt-BR';
		utterance.rate = 0.52;
		utterance.pitch = 1;
		window.speechSynthesis.speak(utterance);
		return true;
	}

	async function playRecordedAudio(url) {
		if (!url) return false;

		const audio = new Audio(url);
		audio.preload = 'auto';

		return new Promise((resolve) => {
			let settled = false;
			const done = (played) => {
				if (settled) return;
				settled = true;
				resolve(played);
			};

			audio.addEventListener('playing', () => done(true), { once: true });
			audio.addEventListener('error', () => done(false), { once: true });
			const playPromise = audio.play();
			if (playPromise && typeof playPromise.then === 'function') {
				playPromise.then(() => done(true)).catch(() => done(false));
			}
			window.setTimeout(() => done(audio.readyState > 0), 2200);
		});
	}

	async function fetchWithTimeout(url, options = {}, timeout = 8000) {
		const controller = new AbortController();
		const id = setTimeout(() => controller.abort(), timeout);
		try {
			const response = await fetch(url, { ...options, signal: controller.signal });
			clearTimeout(id);
			return response;
		} catch (err) {
			clearTimeout(id);
			throw err;
		}
	}

	async function postJson(url, payload) {
		const response = await fetchWithTimeout(url, {
			method: 'POST',
			headers: { 'Content-Type': 'application/json' },
			body: JSON.stringify(payload),
		}, 8000);

		if (!response.ok) {
			throw new Error('HTTP ' + response.status);
		}

		return response;
	}

	function getInputs() {
		return [...card.querySelectorAll('.cloud-input')];
	}

	function isFilled(input) {
		return String(input.value || '').trim().length > 0;
	}

	function updateFlow() {
		const inputs = getInputs();
		inputs.forEach((input, index) => {
			const previousOk = index === 0 || isFilled(inputs[index - 1]);
			input.disabled = finishing || !previousOk;
			input.setAttribute('aria-disabled', String(input.disabled));

			const item = input.closest('.question-item');
			if (item) {
				item.classList.toggle('is-locked', input.disabled);
				item.classList.toggle('is-done', isFilled(input));
			}
		});

		const finishButton = card.querySelector('.finish-button');
		const allFilled = inputs.length === QUESTIONS.length && inputs.every(isFilled);
		if (finishButton) {
			finishButton.disabled = finishing || !allFilled;
			finishButton.textContent = finishing ? 'Enviando...' : 'Finalizar teste';
		}
	}

	function focusNextIfReady(input) {
		if (!isFilled(input)) return;

		const inputs = getInputs();
		const current = inputs.indexOf(input);
		const question = QUESTIONS[current];
		const normalizedTyped = String(input.value || '').replace(/\s+/g, '').length;
		const normalizedExpected = String(question.text || '').replace(/\s+/g, '').length;
		if (normalizedTyped < normalizedExpected) return;

		const next = inputs[current + 1];
		if (next && !next.disabled) {
			window.setTimeout(() => next.focus(), 120);
		}
	}

	async function requestSound(question, buttonEl) {
		if (!question || !buttonEl) return;

		const requestId = 'sound-' + (++soundRequestCounter);
		const payload = {
			id: buttonEl.id,
			role: 'button',
			palavra: question.text,
			aluno: STUDENT,
			createdAt: new Date().toISOString(),
		};

		buttonEl.classList.add('pressed');
		window.setTimeout(() => buttonEl.classList.remove('pressed'), 700);

		if (await playRecordedAudio(question.audio)) return;
		if (speakWord(question.text)) return;
		if (!API_BASE_URL) return;

		try {
			const response = await fetchWithTimeout(buildEndpoint(SOUND_ENDPOINT), {
				method: 'POST',
				headers: { 'Content-Type': 'application/json' },
				body: JSON.stringify(payload),
			}, 10000);

			if (!response.ok) {
				throw new Error('HTTP ' + response.status);
			}

			const blob = await response.blob();
			const audioUrl = URL.createObjectURL(blob);
			const audio = new Audio(audioUrl);
			audio.onended = () => URL.revokeObjectURL(audioUrl);
			await audio.play();
		} catch (error) {
			console.error('Falha ao reproduzir audio:', error, requestId, payload);
		}
	}

	function getPayload(input, question) {
		return {
			id: input.id,
			value: input.value,
			gabarito: question.text,
			source: question.source,
			aluno: STUDENT,
			createdAt: new Date().toISOString(),
		};
	}

	async function submitAll() {
		if (finishing) return;
		const inputs = getInputs();
		if (!inputs.every(isFilled)) return;

		finishing = true;
		updateFlow();

		try {
			for (let index = 0; index < QUESTIONS.length; index += 1) {
				const question = QUESTIONS[index];
				const input = inputs[index];
				const payload = getPayload(input, question);
				const endpoint = payload.source === 'main' ? buildEndpoint(MESSAGE_ENDPOINT) : buildEndpoint(CLOUD_ENDPOINT);
				const requestId = 'submit-' + (++submitTokenCounter);

				if (!API_BASE_URL) {
					console.log('Payload pronto para envio:', requestId, payload);
					continue;
				}
				await postJson(endpoint, payload);
			}

			window.location.href = '/finalizar';
		} catch (error) {
			console.error('Falha ao finalizar teste:', error);
			finishing = false;
			updateFlow();
		}
	}

	function createQuestionItem(question, index) {
		const item = document.createElement('section');
		item.className = 'question-item';

		const badge = document.createElement('div');
		badge.className = 'question-badge';
		badge.textContent = String(index + 1);

		const visual = document.createElement('div');
		visual.className = 'object-figure';
		visual.setAttribute('aria-hidden', 'true');
		visual.textContent = question.visual;

		const controls = document.createElement('div');
		controls.className = 'answer-row';

		const soundButton = document.createElement('button');
		soundButton.id = 'sound-button-' + (index + 1);
		soundButton.className = 'cloud-gif-button gif-button';
		soundButton.type = 'button';
		soundButton.setAttribute('aria-label', 'Tocar som da ' + question.label);

		const gifImg = document.createElement('img');
		gifImg.src = 'som.gif';
		gifImg.alt = 'Tocar som';
		gifImg.className = 'cloud-gif';
		soundButton.appendChild(gifImg);
		soundButton.addEventListener('click', () => requestSound(question, soundButton));

		const input = document.createElement('input');
		input.id = question.source + '-input-' + (index + 1);
		input.type = 'text';
		input.className = 'cloud-input';
		input.autocomplete = 'off';
		input.autocapitalize = 'none';
		input.spellcheck = false;
		input.dataset.gabarito = question.text;
		input.placeholder = '';
		input.setAttribute('aria-label', question.label);
		input.addEventListener('input', () => {
			updateFlow();
			focusNextIfReady(input);
		});

		controls.append(soundButton, input);
		item.append(badge, visual, controls);
		return item;
	}

	function renderQuestions() {
		card.innerHTML = '';
		card.className = 'card test-card multi-question-card';

		const grid = document.createElement('div');
		grid.className = 'question-grid';
		QUESTIONS.forEach((question, index) => {
			grid.appendChild(createQuestionItem(question, index));
		});

		const finishButton = document.createElement('button');
		finishButton.type = 'button';
		finishButton.className = 'finish-button';
		finishButton.textContent = 'Finalizar teste';
		finishButton.addEventListener('click', submitAll);

		card.append(grid, finishButton);
		updateFlow();
		window.setTimeout(() => {
			const firstInput = card.querySelector('.cloud-input');
			if (firstInput) firstInput.focus();
		}, 80);
	}

	renderStudentPanel();
	renderQuestions();
})();
