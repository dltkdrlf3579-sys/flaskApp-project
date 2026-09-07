(function () {
    function inline(parent, text) {
        const fragments = String(text).split(/(\*\*[^*]+\*\*|`[^`]+`)/g);
        fragments.forEach((fragment) => {
            if (fragment.startsWith('**') && fragment.endsWith('**')) {
                const strong = document.createElement('strong');
                strong.textContent = fragment.slice(2, -2);
                parent.appendChild(strong);
            } else if (fragment.startsWith('`') && fragment.endsWith('`')) {
                const code = document.createElement('code');
                code.textContent = fragment.slice(1, -1);
                parent.appendChild(code);
            } else {
                parent.appendChild(document.createTextNode(fragment));
            }
        });
    }

    function renderText(target, text) {
        target.replaceChildren();
        target.classList.add('ai-formatted');
        const lines = String(text).split(/\r?\n/);
        let position = 0;
        while (position < lines.length) {
            const line = lines[position];
            if (line.trim().startsWith('```')) {
                const pre = document.createElement('pre');
                const codeLines = [];
                position += 1;
                while (position < lines.length && !lines[position].trim().startsWith('```')) {
                    codeLines.push(lines[position++]);
                }
                pre.textContent = codeLines.join('\n');
                target.appendChild(pre);
                position += 1;
            } else if (line.includes('|') && position + 1 < lines.length && /^\s*\|?\s*:?-{3,}:?\s*(\|\s*:?-{3,}:?\s*)+\|?\s*$/.test(lines[position + 1])) {
                const wrapper = document.createElement('div');
                wrapper.className = 'ai-table-wrap';
                const table = document.createElement('table');
                const cells = (value) => value.trim().replace(/^\|/, '').replace(/\|$/, '').split('|');
                const addRow = (value, heading) => {
                    const row = document.createElement('tr');
                    cells(value).forEach((cell) => {
                        const node = document.createElement(heading ? 'th' : 'td');
                        inline(node, cell.trim());
                        row.appendChild(node);
                    });
                    table.appendChild(row);
                };
                addRow(line, true);
                position += 2;
                while (position < lines.length && lines[position].includes('|') && lines[position].trim()) {
                    addRow(lines[position++], false);
                }
                wrapper.appendChild(table);
                target.appendChild(wrapper);
            } else if (/^\s*(?:[-*] |\d+\. )/.test(line)) {
                const ordered = /^\s*\d+\. /.test(line);
                const list = document.createElement(ordered ? 'ol' : 'ul');
                const pattern = ordered ? /^\s*\d+\. / : /^\s*[-*] /;
                while (position < lines.length && pattern.test(lines[position])) {
                    const item = document.createElement('li');
                    inline(item, lines[position++].replace(pattern, ''));
                    list.appendChild(item);
                }
                target.appendChild(list);
            } else {
                const heading = line.match(/^(#{1,4})\s+(.+)$/);
                if (line.trim()) {
                    const block = document.createElement(heading ? 'h' + Math.min(heading[1].length + 2, 6) : 'p');
                    inline(block, heading ? heading[2] : line);
                    target.appendChild(block);
                }
                position += 1;
            }
        }
    }

    function safeResourceUrl(value) {
        if (typeof value !== 'string' || !/^\/api\/ai-assistant\/materials\/[a-f0-9]{24}\/(?:download|image|pages\/[1-9][0-9]*\.png|files\/[a-f0-9]{24})$/.test(value)) return null;
        return value;
    }

    function renderResources(parent, resources) {
        parent.querySelectorAll(':scope > .ai-resources').forEach((node) => node.remove());
        if (!resources || typeof resources !== 'object') return;
        const panel = document.createElement('div');
        panel.className = 'ai-resources';
        for (const [key, title] of [['sources', '확인한 출처'], ['downloads', '관련 파일'], ['images', '관련 페이지 / 이미지']]) {
            const items = Array.isArray(resources[key]) ? resources[key].slice(0, 20) : [];
            const valid = items.filter((item) => item && safeResourceUrl(item.url));
            if (!valid.length) continue;
            const heading = document.createElement('h4');
            heading.textContent = title;
            panel.appendChild(heading);
            const group = document.createElement('div');
            group.className = key === 'images' ? 'ai-image-grid' : 'ai-file-list';
            valid.forEach((item) => {
                const link = document.createElement('a');
                link.href = safeResourceUrl(item.url);
                link.target = '_blank';
                link.rel = 'noopener';
                link.className = 'ai-resource-card';
                const caption = document.createElement('span');
                caption.textContent = (item.label ? '[' + item.label + '] ' : '') + (item.title || '자료') + (item.page ? ' · ' + item.page + '쪽' : '');
                if (key === 'images') {
                    const picture = document.createElement('img');
                    picture.src = link.href;
                    picture.alt = caption.textContent;
                    picture.loading = 'lazy';
                    picture.addEventListener('error', () => {
                        picture.remove();
                        const error = document.createElement('span');
                        error.textContent = '이미지를 열지 못했습니다. 원본 파일 또는 서버 자료 설정을 확인하세요.';
                        link.appendChild(error);
                    }, { once: true });
                    link.appendChild(picture);
                }
                link.appendChild(caption);
                group.appendChild(link);
            });
            panel.appendChild(group);
        }
        if (panel.childElementCount) parent.appendChild(panel);
    }

    window.PortalAiRender = { text: renderText, resources: renderResources };
}());
