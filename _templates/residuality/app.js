(function () {
    'use strict';

    const model = window.RESIDUALITY_MODEL || {};
    const catalog = Array.isArray(window.RESIDUALITY_CATALOG) ? window.RESIDUALITY_CATALOG : [];
    const metadata = model.metadata || {};
    const stressors = Array.isArray(model.stressors) ? model.stressors : [];

    const TYPE_META = {
        vision: { label: 'Vision', plural: 'Visions', category: 'strategy', order: 1 },
        job: { label: 'Job to be done', plural: 'Jobs to be done', category: 'strategy', order: 2 },
        journey: { label: 'Journey step', plural: 'Journey steps', category: 'strategy', order: 3 },
        kpi: { label: 'KPI', plural: 'KPIs', category: 'strategy', order: 4 },
        product: { label: 'Product', plural: 'Products', category: 'implementation', order: 5 },
        stream: { label: 'Product stream', plural: 'Product streams', category: 'implementation', order: 6 },
        brick: { label: 'Product brick', plural: 'Product bricks', category: 'implementation', order: 7 },
        team: { label: 'Team', plural: 'Teams', category: 'organization', order: 8 },
        competitor: { label: 'Competitor', plural: 'Competition', category: 'strategy', order: 9 }
    };

    const CATEGORY_META = {
        strategy: {
            label: 'Strategy & Vision',
            description: 'Customer goals, journeys, measures, and competitive positioning.',
            order: 1
        },
        implementation: {
            label: 'Implementation',
            description: 'Products, product streams, and product bricks that must work differently.',
            order: 2
        },
        organization: {
            label: 'Organization',
            description: 'Team ownership, responsibilities, and coordination.',
            order: 3
        }
    };

    const STATUS_META = {
        candidate: { label: 'Proposed change', short: 'Proposed' },
        integrated: { label: 'Built into the design', short: 'Built in' },
        'already-survived': { label: 'Already handled', short: 'Already handled' }
    };

    const catalogMap = new Map(catalog.map(function (item) {
        return [targetKey(item.type, item.id), item];
    }));
    const stressorMap = new Map(stressors.map(function (stressor) {
        return [stressor.id, stressor];
    }));

    const state = {
        view: 'analysis',
        search: '',
        group: '',
        status: '',
        matrixType: catalog.some(function (item) { return item.type === 'brick'; }) ? 'brick' : firstCatalogType()
    };

    function targetKey(type, id) {
        return String(type || '') + ':' + String(id || '');
    }

    function firstCatalogType() {
        const ordered = Object.keys(TYPE_META).sort(function (a, b) {
            return TYPE_META[a].order - TYPE_META[b].order;
        });
        return ordered.find(function (type) {
            return catalog.some(function (item) { return item.type === type; });
        }) || 'brick';
    }

    function escapeHtml(value) {
        return String(value == null ? '' : value)
            .replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;')
            .replace(/"/g, '&quot;')
            .replace(/'/g, '&#039;');
    }

    function typeMeta(type) {
        return TYPE_META[type] || { label: type || 'Target', plural: type || 'Targets', category: 'strategy', order: 99 };
    }

    function categoryMeta(category) {
        return CATEGORY_META[category] || {
            label: category || 'Other',
            description: 'Other affected parts of the productscape.',
            order: 99
        };
    }

    function statusMeta(status) {
        return STATUS_META[status] || STATUS_META.candidate;
    }

    function catalogTarget(impact) {
        return catalogMap.get(targetKey(impact.targetType, impact.targetId)) || {
            type: impact.targetType,
            id: impact.targetId,
            name: impact.targetId,
            description: '',
            href: '',
            context: ''
        };
    }

    function targetNameHtml(target) {
        const name = escapeHtml(target.name || target.id);
        if (target.href) {
            return '<a href="' + escapeHtml(target.href) + '">' + name + '</a>';
        }
        return '<strong>' + name + '</strong>';
    }

    function allImpactTargets(sourceStressors) {
        const keys = new Set();
        sourceStressors.forEach(function (stressor) {
            (stressor.impacts || []).forEach(function (impact) {
                keys.add(targetKey(impact.targetType, impact.targetId));
            });
        });
        return keys;
    }

    function residualIndex() {
        const test = model.freshStressorTest;
        if (!test || !test.stressors) return null;
        return (Number(test.residualSurvivals) - Number(test.naiveSurvivals)) / Number(test.stressors);
    }

    function formatIndex(value) {
        if (value == null || Number.isNaN(value)) return 'Not run';
        const normalized = Math.abs(value) < 0.005 ? 0 : value;
        return (normalized > 0 ? '+' : '') + normalized.toFixed(2);
    }

    function renderMetrics() {
        const candidateCount = stressors.filter(function (item) { return (item.status || 'candidate') === 'candidate'; }).length;
        const integratedCount = stressors.filter(function (item) { return item.status === 'integrated'; }).length;
        const loopingCount = stressors.filter(function (item) { return item.status === 'already-survived'; }).length;
        const impactedCount = allImpactTargets(stressors).size;
        const ri = residualIndex();
        const test = model.freshStressorTest;
        const cards = [
            { label: 'Situations tested', value: stressors.length, note: 'Outside changes explored' },
            { label: 'Changes identified', value: candidateCount + integratedCount, note: candidateCount + ' proposed · ' + integratedCount + ' built in' },
            { label: 'Already handled', value: loopingCount, note: 'Covered by changes made for earlier tests', className: 'looping' },
            { label: 'Affected items', value: impactedCount, note: 'Across strategy, implementation, and organization' },
            {
                label: 'Adaptability score',
                value: formatIndex(ri),
                note: test
                    ? test.stressors + ' new tests · ' + test.naiveSurvivals + ' handled before / ' + test.residualSurvivals + ' handled after'
                    : 'Run with a fresh set of tests after adapting the design',
                className: 'index'
            }
        ];
        document.getElementById('metricGrid').innerHTML = cards.map(function (card) {
            return '<article class="metric-card ' + escapeHtml(card.className || '') + '">' +
                '<div class="metric-label">' + escapeHtml(card.label) + '</div>' +
                '<div class="metric-value">' + escapeHtml(card.value) + '</div>' +
                '<div class="metric-note">' + escapeHtml(card.note) + '</div>' +
                '</article>';
        }).join('');
    }

    function renderArchitecture() {
        const naive = metadata.naiveArchitecture || 'Describe the simplest product and architecture that satisfies the currently stated problem.';
        const residual = metadata.residualArchitecture || 'Combine the useful changes into one coherent, more adaptable product and architecture.';
        document.getElementById('architectureGrid').innerHTML =
            '<article class="architecture-card naive">' +
            '<div class="architecture-label">Before the stress test</div>' +
            '<h3>Current design</h3>' +
            '<p>' + escapeHtml(naive) + '</p>' +
            '</article>' +
            '<div class="architecture-arrow" aria-hidden="true">→</div>' +
            '<article class="architecture-card residual">' +
            '<div class="architecture-label">After applying the useful changes</div>' +
            '<h3>Adapted design</h3>' +
            '<p>' + escapeHtml(residual) + '</p>' +
            '</article>';
    }

    function stressorSearchText(stressor) {
        const targetText = (stressor.impacts || []).map(function (impact) {
            const target = catalogTarget(impact);
            return [target.name, target.context, impact.effect, typeMeta(impact.targetType).label].join(' ');
        }).join(' ');
        const reusedText = (stressor.reusesResidueIds || []).map(function (id) {
            const reused = stressorMap.get(id);
            return reused ? reused.name : id;
        }).join(' ');
        return [
            stressor.id,
            stressor.name,
            stressor.group,
            stressor.detection,
            stressor.attractor,
            stressor.businessReaction,
            stressor.residue,
            targetText,
            reusedText
        ].join(' ').toLowerCase();
    }

    function filteredStressors() {
        return stressors.filter(function (stressor) {
            if (state.group && String(stressor.group || '') !== state.group) return false;
            if (state.status && String(stressor.status || 'candidate') !== state.status) return false;
            if (state.search && stressorSearchText(stressor).indexOf(state.search) === -1) return false;
            return true;
        });
    }

    function sortedImpacts(impacts) {
        return (impacts || []).slice().sort(function (a, b) {
            const typeDifference = typeMeta(a.targetType).order - typeMeta(b.targetType).order;
            if (typeDifference) return typeDifference;
            return String(catalogTarget(a).name).localeCompare(String(catalogTarget(b).name));
        });
    }

    function renderImpactLine(impact) {
        const target = catalogTarget(impact);
        return '<div class="impact-line">' +
            '<div class="impact-line-head">' +
            '<span class="type-chip">' + escapeHtml(typeMeta(impact.targetType).label) + '</span>' +
            targetNameHtml(target) +
            '</div>' +
            '<p><span class="change-prefix">What changes:</span> ' + escapeHtml(impact.effect) + '</p>' +
            '</div>';
    }

    function renderStressorImpactGroups(impacts) {
        const grouped = {};
        impacts.forEach(function (impact) {
            const category = typeMeta(impact.targetType).category;
            if (!grouped[category]) grouped[category] = [];
            grouped[category].push(impact);
        });

        return '<div class="stressor-impact-groups">' + Object.keys(CATEGORY_META)
            .sort(function (a, b) { return categoryMeta(a).order - categoryMeta(b).order; })
            .map(function (category) {
                const categoryImpacts = grouped[category] || [];
                return '<section class="stressor-impact-group">' +
                    '<div class="stressor-impact-group-head">' +
                    '<strong>' + escapeHtml(categoryMeta(category).label) + '</strong>' +
                    '<span>' + categoryImpacts.length + ' change' + (categoryImpacts.length === 1 ? '' : 's') + '</span>' +
                    '</div>' +
                    '<p class="stressor-impact-group-description">' + escapeHtml(categoryMeta(category).description) + '</p>' +
                    (categoryImpacts.length
                        ? '<div class="impact-columns">' + categoryImpacts.map(renderImpactLine).join('') + '</div>'
                        : '<div class="stressor-impact-group-empty">No mapped changes</div>') +
                    '</section>';
            }).join('') + '</div>';
    }

    function renderReuseRow(stressor) {
        const reusedIds = stressor.reusesResidueIds || [];
        if (!reusedIds.length) return '';
        const chips = reusedIds.map(function (id) {
            const reused = stressorMap.get(id);
            const label = reused ? reused.name : id;
            return '<span class="reuse-chip" title="' + escapeHtml(id) + '">' + escapeHtml(label) + '</span>';
        }).join('');
        return '<div class="reuse-row"><strong>Already handled using earlier changes</strong>' + chips + '</div>';
    }

    function renderStressorMedia(stressor) {
        const media = Array.isArray(stressor.media) ? stressor.media : [];
        const image = media.find(function (item) {
            return item && item.type === 'image' && item.src;
        });
        if (!image) return '';

        const alt = image.alt || image.title || ('Illustration of ' + stressor.name);
        return '<figure class="stressor-media">' +
            '<img src="' + escapeHtml(image.src) + '" alt="' + escapeHtml(alt) + '" loading="lazy" decoding="async">' +
            (image.title ? '<figcaption>' + escapeHtml(image.title) + '</figcaption>' : '') +
            '</figure>';
    }

    function renderStressorCard(stressor, originalIndex) {
        const status = stressor.status || 'candidate';
        const impacts = sortedImpacts(stressor.impacts);
        return '<article class="stressor-card ' + escapeHtml(status) + '" id="stressor-' + escapeHtml(stressor.id) + '">' +
            '<div class="stressor-head">' +
            '<div>' +
            '<div class="stressor-kicker">' +
            '<span class="sequence">#' + String(originalIndex + 1).padStart(2, '0') + ' · ' + escapeHtml(stressor.id) + '</span>' +
            '<span class="context-chip">' + escapeHtml(stressor.group || 'Business context') + '</span>' +
            '<span class="status-chip ' + escapeHtml(status) + '">' + escapeHtml(statusMeta(status).label) + '</span>' +
            '</div>' +
            '<h3>' + escapeHtml(stressor.name) + '</h3>' +
            '</div>' +
            '<div class="impact-count"><strong>' + impacts.length + '</strong><span>affected item' + (impacts.length === 1 ? '' : 's') + '</span></div>' +
            '</div>' +
            renderStressorMedia(stressor) +
            '<div class="stressor-chain">' +
            '<div class="chain-step"><div class="chain-label">What would tell us</div><p>' + escapeHtml(stressor.detection) + '</p></div>' +
            '<div class="chain-step"><div class="chain-label">Situation the business enters</div><p>' + escapeHtml(stressor.attractor) + '</p></div>' +
            '<div class="chain-step"><div class="chain-label">What the business does</div><p>' + escapeHtml(stressor.businessReaction) + '</p></div>' +
            '<div class="chain-step"><div class="chain-label">What we change</div><p>' + escapeHtml(stressor.residue) + '</p></div>' +
            '</div>' +
            renderReuseRow(stressor) +
            '<div class="stressor-impacts">' +
            '<div class="impact-section-label">Where that change appears in the productscape</div>' +
            (impacts.length ? renderStressorImpactGroups(impacts) : '<div class="empty-state"><strong>No affected items mapped</strong>Describe the concrete change, then link it to strategy, products, streams, bricks, teams, or competition.</div>') +
            '</div>' +
            '</article>';
    }

    function renderStressors() {
        const visible = filteredStressors();
        const list = document.getElementById('stressorList');
        const empty = document.getElementById('analysisEmpty');
        list.innerHTML = visible.map(function (stressor) {
            return renderStressorCard(stressor, stressors.indexOf(stressor));
        }).join('');
        list.querySelectorAll('.stressor-media img').forEach(function (image) {
            image.addEventListener('error', function () {
                const figure = image.closest('.stressor-media');
                if (figure) figure.hidden = true;
            }, { once: true });
        });

        if (visible.length) {
            empty.hidden = true;
        } else {
            empty.hidden = false;
            empty.innerHTML = stressors.length
                ? '<strong>No stress tests match these filters</strong>Clear a filter or use a broader search term.'
                : '<strong>No stress tests have been added yet</strong>Add <code>residuality/residuality.json</code> to this domain. Start with a credible outside change—such as a new customer type, regulation, competitor move, or physical event—and describe what the business and product would need to do differently.';
        }
    }

    function buildImpactsByTarget(sourceStressors) {
        const targetMap = new Map();
        sourceStressors.forEach(function (stressor) {
            (stressor.impacts || []).forEach(function (impact) {
                const key = targetKey(impact.targetType, impact.targetId);
                if (!targetMap.has(key)) {
                    targetMap.set(key, { target: catalogTarget(impact), entries: [] });
                }
                targetMap.get(key).entries.push({ stressor: stressor, impact: impact });
            });
        });
        return Array.from(targetMap.values());
    }

    function renderImpactSummary(groups) {
        const counts = {};
        Object.keys(CATEGORY_META).forEach(function (category) { counts[category] = 0; });
        groups.forEach(function (entry) {
            counts[typeMeta(entry.target.type).category] += 1;
        });
        document.getElementById('impactSummary').innerHTML = Object.keys(CATEGORY_META)
            .sort(function (a, b) { return categoryMeta(a).order - categoryMeta(b).order; })
            .map(function (category) {
                return '<div class="impact-summary-card"><strong>' + counts[category] + '</strong><span>' + escapeHtml(categoryMeta(category).label) + ' items affected</span></div>';
            }).join('');
    }

    function renderTargetCard(entry) {
        const target = entry.target;
        const impacts = entry.entries.slice().sort(function (a, b) {
            return String(a.stressor.name).localeCompare(String(b.stressor.name));
        });
        return '<article class="target-card">' +
            '<div class="target-card-head">' +
            '<div class="target-card-title">' +
            '<span class="type-chip">' + escapeHtml(typeMeta(target.type).label) + '</span> ' +
            targetNameHtml(target) +
            (target.context ? '<div class="target-context" title="' + escapeHtml(target.context) + '">' + escapeHtml(target.context) + '</div>' : '') +
            '</div>' +
            '<span class="count-chip">' + impacts.length + ' test' + (impacts.length === 1 ? '' : 's') + '</span>' +
            '</div>' +
            '<div class="target-impact-list">' + impacts.map(function (item) {
                return '<div class="target-impact">' +
                    '<strong>Outside change: ' + escapeHtml(item.stressor.name) + '</strong>' +
                    '<span class="change-prefix">What changes:</span> ' + escapeHtml(item.impact.effect) +
                    '</div>';
            }).join('') + '</div>' +
            '</article>';
    }

    function renderImpacts() {
        const entries = buildImpactsByTarget(filteredStressors());
        renderImpactSummary(entries);
        const container = document.getElementById('impactGroups');
        const empty = document.getElementById('impactEmpty');

        if (!entries.length) {
            container.innerHTML = '';
            empty.hidden = false;
            empty.innerHTML = '<strong>No affected items to show</strong>Each test can explain what changes in visions, jobs, journeys, KPIs, products, streams, bricks, teams, and competition.';
            return;
        }
        empty.hidden = true;

        const grouped = {};
        entries.forEach(function (entry) {
            const category = typeMeta(entry.target.type).category;
            if (!grouped[category]) grouped[category] = [];
            grouped[category].push(entry);
        });

        container.innerHTML = Object.keys(grouped)
            .sort(function (a, b) { return categoryMeta(a).order - categoryMeta(b).order; })
            .map(function (category) {
                const categoryEntries = grouped[category].sort(function (a, b) {
                    const typeDifference = typeMeta(a.target.type).order - typeMeta(b.target.type).order;
                    if (typeDifference) return typeDifference;
                    return String(a.target.name).localeCompare(String(b.target.name));
                });
                return '<section class="impact-group">' +
                    '<div class="impact-group-head"><h3>' + escapeHtml(categoryMeta(category).label) + '</h3><span class="count-chip">' + categoryEntries.length + ' affected</span></div>' +
                    '<div class="target-grid">' + categoryEntries.map(renderTargetCard).join('') + '</div>' +
                    '</section>';
            }).join('');
    }

    function availableMatrixTypes() {
        return Object.keys(TYPE_META)
            .filter(function (type) { return catalog.some(function (item) { return item.type === type; }); })
            .sort(function (a, b) { return typeMeta(a).order - typeMeta(b).order; });
    }

    function renderMatrixTypePicker() {
        const types = availableMatrixTypes();
        if (types.length && types.indexOf(state.matrixType) === -1) state.matrixType = types[0];
        document.getElementById('matrixTypePicker').innerHTML = types.map(function (type) {
            const count = catalog.filter(function (item) { return item.type === type; }).length;
            return '<button type="button" class="matrix-type-button ' + (state.matrixType === type ? 'active' : '') + '" data-matrix-type="' + escapeHtml(type) + '">' + escapeHtml(typeMeta(type).plural) + ' · ' + count + '</button>';
        }).join('');
        document.querySelectorAll('[data-matrix-type]').forEach(function (button) {
            button.addEventListener('click', function () {
                state.matrixType = button.getAttribute('data-matrix-type');
                renderMatrixTypePicker();
                renderMatrix();
            });
        });
    }

    function renderMatrixCallouts(rows, targets, rowTotals, columnTotals) {
        const coupledRows = rowTotals.filter(function (total) { return total > 1; }).length;
        const maxColumn = columnTotals.length ? Math.max.apply(null, columnTotals) : 0;
        const mostSensitive = targets.filter(function (_, index) { return columnTotals[index] === maxColumn && maxColumn > 0; });
        const zeroCount = columnTotals.filter(function (total) { return total === 0; }).length;
        const sensitiveText = mostSensitive.length
            ? mostSensitive.slice(0, 2).map(function (item) { return item.name; }).join(', ') + (mostSensitive.length > 2 ? ' +' + (mostSensitive.length - 2) : '')
            : 'No affected items yet';
        document.getElementById('matrixCallouts').innerHTML =
            '<div class="matrix-callout"><strong>' + coupledRows + '</strong>outside change' + (coupledRows === 1 ? '' : 's') + ' affect multiple ' + escapeHtml(typeMeta(state.matrixType).plural.toLowerCase()) + '</div>' +
            '<div class="matrix-callout"><strong>' + escapeHtml(sensitiveText) + '</strong>affected most often · ' + maxColumn + ' test' + (maxColumn === 1 ? '' : 's') + '</div>' +
            '<div class="matrix-callout"><strong>' + zeroCount + '</strong>' + escapeHtml(typeMeta(state.matrixType).plural.toLowerCase()) + ' not affected by the current tests</div>';
    }

    function renderMatrix() {
        const rows = filteredStressors();
        const targets = catalog.filter(function (item) { return item.type === state.matrixType; })
            .sort(function (a, b) { return String(a.name).localeCompare(String(b.name)); });
        const container = document.getElementById('matrixContainer');
        const empty = document.getElementById('matrixEmpty');

        if (!rows.length || !targets.length) {
            container.innerHTML = '';
            container.hidden = true;
            document.getElementById('matrixCallouts').innerHTML = '';
            empty.hidden = false;
            empty.innerHTML = '<strong>No shared-impact matrix can be built for this view</strong>Map at least one visible test to an item in the selected category.';
            return;
        }

        container.hidden = false;
        empty.hidden = true;
        const rowTotals = [];
        const columnTotals = targets.map(function () { return 0; });
        const hits = rows.map(function (stressor) {
            const impactKeys = new Set((stressor.impacts || []).map(function (impact) {
                return targetKey(impact.targetType, impact.targetId);
            }));
            const rowHits = targets.map(function (target, index) {
                const hit = impactKeys.has(targetKey(target.type, target.id));
                if (hit) columnTotals[index] += 1;
                return hit;
            });
            rowTotals.push(rowHits.filter(Boolean).length);
            return rowHits;
        });
        const maxRow = Math.max.apply(null, rowTotals);
        const maxColumn = Math.max.apply(null, columnTotals);

        let html = '<table class="matrix-table"><thead><tr><th class="row-label">Outside change</th>';
        targets.forEach(function (target) {
            html += '<th title="' + escapeHtml(target.name) + '"><span class="matrix-column-label">' + escapeHtml(target.name) + '</span></th>';
        });
        html += '<th class="matrix-total">Total</th></tr></thead><tbody>';
        rows.forEach(function (stressor, rowIndex) {
            const total = rowTotals[rowIndex];
            html += '<tr class="matrix-row ' + (total > 1 ? 'coupled' : '') + '"><th class="row-label" title="' + escapeHtml(stressor.attractor) + '">' + escapeHtml(stressor.name) + '</th>';
            hits[rowIndex].forEach(function (hit) {
                html += '<td class="matrix-cell ' + (hit ? 'hit' : '') + '">' + (hit ? '1' : '·') + '</td>';
            });
            html += '<td class="matrix-total ' + (total === maxRow && maxRow > 1 ? 'high' : '') + '">' + total + '</td></tr>';
        });
        html += '</tbody><tfoot><tr><th class="row-label">Tests affecting each item</th>';
        columnTotals.forEach(function (total) {
            const className = total === 0 ? 'zero' : (total === maxColumn && maxColumn > 1 ? 'high' : '');
            html += '<td class="' + className + '">' + total + '</td>';
        });
        html += '<td class="matrix-total">Total=' + columnTotals.reduce(function (sum, total) { return sum + total; }, 0) + '</td></tr></tfoot></table>';
        container.innerHTML = html;
        renderMatrixCallouts(rows, targets, rowTotals, columnTotals);
    }

    function renderTriggers() {
        const triggers = [
            ['One change affects many items', 'Coordinate the response and check whether responsibilities are too tightly connected.'],
            ['One item changes repeatedly', 'It may carry too many responsibilities, or it may be intentionally central and need extra protection.'],
            ['Several items always change together', 'Their boundary may be unclear, duplicated, or missing a layer that could isolate change.'],
            ['Many items change for many tests', 'The product may be too tightly connected; revisit how it is divided into products, streams, and bricks.'],
            ['Combine outside changes', 'Test two changed conditions together to reveal effects that neither creates on its own.'],
            ['Untouched items', 'Add different tests before assuming that these items will never need to change.']
        ];
        document.getElementById('triggerGrid').innerHTML = triggers.map(function (trigger, index) {
            return '<article class="trigger-card"><strong>' + (index + 1) + '. ' + escapeHtml(trigger[0]) + '</strong>' + escapeHtml(trigger[1]) + '</article>';
        }).join('');
    }

    function renderMethodMetadata() {
        const source = metadata.source || {};
        const sourceLink = document.getElementById('sourceLink');
        if (source.url) {
            sourceLink.href = source.url;
        } else {
            sourceLink.hidden = true;
        }
        document.getElementById('sourceCitation').textContent = [source.author, source.title, source.year].filter(Boolean).join(' · ');

        const result = document.getElementById('methodIndexResult');
        const ri = residualIndex();
        if (ri == null) {
            result.innerHTML = '<strong>Not run</strong>No fresh set of tests has been recorded for this productscape.';
        } else {
            const test = model.freshStressorTest;
            result.innerHTML = '<strong>' + escapeHtml(formatIndex(ri)) + '</strong>' +
                escapeHtml(test.residualSurvivals + ' handled after minus ' + test.naiveSurvivals + ' handled before, across ' + test.stressors + ' new tests.');
        }
    }

    function populateGroupFilter() {
        const groups = Array.from(new Set(stressors.map(function (stressor) {
            return String(stressor.group || 'Business context');
        }))).sort();
        const select = document.getElementById('groupFilter');
        select.innerHTML = '<option value="">All business contexts</option>' + groups.map(function (group) {
            return '<option value="' + escapeHtml(group) + '">' + escapeHtml(group) + '</option>';
        }).join('');
    }

    function updateFilterSummary() {
        const visible = filteredStressors().length;
        const filtersActive = Boolean(state.search || state.group || state.status);
        document.getElementById('filterSummary').textContent = filtersActive
            ? 'Showing ' + visible + ' of ' + stressors.length + ' tests'
            : stressors.length + ' stress test' + (stressors.length === 1 ? '' : 's');
    }

    function renderFilteredViews() {
        renderStressors();
        renderImpacts();
        renderMatrix();
        updateFilterSummary();
    }

    function activateView(view, updateHash) {
        if (['analysis', 'impacts', 'contagion', 'method'].indexOf(view) === -1) view = 'analysis';
        state.view = view;
        document.querySelectorAll('[data-view-panel]').forEach(function (panel) {
            const active = panel.getAttribute('data-view-panel') === view;
            panel.hidden = !active;
            panel.classList.toggle('active', active);
        });
        document.querySelectorAll('[data-view]').forEach(function (button) {
            const active = button.getAttribute('data-view') === view;
            button.classList.toggle('active', active);
            button.setAttribute('aria-selected', active ? 'true' : 'false');
        });
        document.getElementById('filterBar').hidden = view === 'method';
        if (updateHash) history.replaceState(null, '', '#' + view);
    }

    function wireEvents() {
        document.querySelectorAll('[data-view]').forEach(function (button) {
            button.addEventListener('click', function () {
                activateView(button.getAttribute('data-view'), true);
            });
        });
        document.getElementById('searchInput').addEventListener('input', function (event) {
            state.search = event.target.value.trim().toLowerCase();
            renderFilteredViews();
        });
        document.getElementById('groupFilter').addEventListener('change', function (event) {
            state.group = event.target.value;
            renderFilteredViews();
        });
        document.getElementById('statusFilter').addEventListener('change', function (event) {
            state.status = event.target.value;
            renderFilteredViews();
        });
        document.getElementById('clearFilters').addEventListener('click', function () {
            state.search = '';
            state.group = '';
            state.status = '';
            document.getElementById('searchInput').value = '';
            document.getElementById('groupFilter').value = '';
            document.getElementById('statusFilter').value = '';
            renderFilteredViews();
        });
        window.addEventListener('hashchange', function () {
            activateView(window.location.hash.slice(1) || 'analysis', false);
        });
    }

    function initialize() {
        document.getElementById('heroDescription').textContent = metadata.description || 'Explore how this product would need to change when customers, markets, regulation, operations, or competitors behave differently from today\'s assumptions.';
        populateGroupFilter();
        renderMetrics();
        renderArchitecture();
        renderMatrixTypePicker();
        renderTriggers();
        renderMethodMetadata();
        renderFilteredViews();
        wireEvents();
        activateView(window.location.hash.slice(1) || 'analysis', false);
    }

    initialize();
}());
