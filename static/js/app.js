/* Provenance Guard — Interactive Client Script */
document.addEventListener("DOMContentLoaded", () => {
    // DOM Elements
    const form = document.getElementById("submission-form");
    const textInput = document.getElementById("submission-text");
    const typeSelect = document.getElementById("content-type");
    const metadataInput = document.getElementById("submission-metadata");
    const creatorInput = document.getElementById("creator-id");
    const submitBtn = document.getElementById("btn-submit");
    const submitSpinner = document.getElementById("submit-spinner");
    
    const resultBox = document.getElementById("result-container");
    const banner = document.getElementById("transparency-banner");
    const bannerTitle = document.getElementById("banner-title");
    const bannerText = document.getElementById("banner-text");
    const bannerConfidence = document.getElementById("banner-confidence");
    const bannerIcon = document.getElementById("banner-icon");
    const resultStatusBadge = document.getElementById("result-status-badge");
    const signalsGrid = document.getElementById("signals-grid");
    const btnOpenAppeal = document.getElementById("btn-open-appeal");
    const btnIssueCert = document.getElementById("btn-issue-cert");

    // Modal elements
    const appealModal = document.getElementById("appeal-modal");
    const modalClose = document.getElementById("modal-close");
    const modalCancel = document.getElementById("modal-cancel");
    const appealForm = document.getElementById("appeal-form");
    const appealSubIdInput = document.getElementById("appeal-submission-id");
    const appealCreatorInput = document.getElementById("appeal-creator");
    const appealReasoningInput = document.getElementById("appeal-reasoning");
    const appealEvidenceInput = document.getElementById("appeal-evidence");
    const appealAssistanceSelect = document.getElementById("appeal-assistance");

    const certModal = document.getElementById("cert-modal");
    const certModalClose = document.getElementById("cert-modal-close");
    const certBody = document.getElementById("cert-body");

    let currentSubmission = null;

    // Presets for quick evaluation
    const PRESETS = {
        human: {
            type: "blog_post",
            creator: "elena_russo",
            text: "My grandmother always said you can smell rain before the sky admits it. Standing on the crumbling porch in Duluth, the pine needles felt like damp needles through my socks. I hadn’t planned to return here after the estate sale—too many ghost echoes in the hallway, too much linoleum peeling like sunburn. But when the lock turned easily under my thumb, I realized she had never changed it. Forty years of winters, and the brass had simply given up resisting.",
            metadata: '{"platform": "personal_blog", "revision_count": 4, "draft_time_minutes": 45}'
        },
        ai: {
            type: "blog_post",
            creator: "digital_blogger",
            text: "In conclusion, it is important to delve into the vibrant tapestry of human innovation, which stands as a testament to our collective resilience. Furthermore, technology plays a pivotal role in shaping modern creative discourse. As we navigate the complexities of an ever-evolving digital landscape, fostering creative synergy serves as a beacon of hope for artists worldwide. Moreover, it is worth noting that collaboration underscores our mutual potential.",
            metadata: '{"platform": "web_auto", "account_age_days": 2, "author_karma": 0}'
        },
        uncertain: {
            type: "short_story",
            creator: "hybrid_writer",
            text: "The engine coughed once, then died at the intersection. In conclusion, the city seemed to stop breathing with it. Rain began to slick the asphalt as streetlights flickered to life. While the quiet was heavy, navigating through the damp streets revealed a strange calm. He checked his rearview mirror, tapping his fingers against the worn steering wheel, wondering if the old alternator would survive another winter night.",
            metadata: '{"platform": "medium", "revision_count": 1, "draft_time_minutes": 10}'
        }
    };

    // Preset button handlers
    document.getElementById("preset-human").addEventListener("click", () => applyPreset("human"));
    document.getElementById("preset-ai").addEventListener("click", () => applyPreset("ai"));
    document.getElementById("preset-uncertain").addEventListener("click", () => applyPreset("uncertain"));

    function applyPreset(name) {
        const p = PRESETS[name];
        typeSelect.value = p.type;
        creatorInput.value = p.creator;
        textInput.value = p.text;
        metadataInput.value = p.metadata;
    }

    // Submission handler
    form.addEventListener("submit", async (e) => {
        e.preventDefault();
        const content = textInput.value.trim();
        if (content.length < 10) {
            alert("Please enter at least 10 characters.");
            return;
        }

        let metadata = {};
        if (metadataInput.value.trim()) {
            try {
                metadata = JSON.parse(metadataInput.value.trim());
            } catch (err) {
                alert("Invalid JSON in platform metadata field. Please correct or leave empty.");
                return;
            }
        }

        submitBtn.disabled = true;
        submitBtn.innerText = "Analyzing Multi-Signal Pipeline...";

        try {
            const response = await fetch("/submit", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    content: content,
                    content_type: typeSelect.value,
                    creator_id: creatorInput.value,
                    metadata: metadata
                })
            });

            if (response.status === 429) {
                const errData = await response.json();
                alert(`Rate limit exceeded: ${errData.message}`);
                return;
            }

            if (!response.ok) {
                const errData = await response.json();
                throw new Error(errData.message || errData.error || "Submission failed");
            }

            const data = await response.json();
            currentSubmission = data;
            renderResult(data);
            appendLogToTable(data, content);
        } catch (error) {
            alert(`Error: ${error.message}`);
        } finally {
            submitBtn.disabled = false;
            submitBtn.innerText = "Analyze Attribution (POST /submit)";
        }
    });

    function renderResult(data) {
        resultBox.classList.remove("hidden");

        // Set Banner Theme
        banner.className = `transparency-banner banner-${data.attribution}`;
        bannerTitle.innerText = data.transparency_badge;
        bannerText.innerText = `"${data.transparency_label}"`;
        bannerConfidence.innerText = `Confidence: ${(data.confidence_score * 100).toFixed(1)}%`;

        let icon = "🏷️";
        if (data.attribution === "human") icon = "🛡️";
        else if (data.attribution === "ai") icon = "🤖";
        else if (data.attribution === "uncertain") icon = "⚖️";
        bannerIcon.innerText = icon;

        resultStatusBadge.className = `tag tag-${data.attribution}`;
        resultStatusBadge.innerText = `${data.attribution.toUpperCase()} (Composite AI Score: ${(data.composite_ai_score * 100).toFixed(1)}%)`;

        // Configure actions
        if (data.attribution === "human") {
            btnOpenAppeal.classList.add("hidden");
            btnIssueCert.classList.remove("hidden");
        } else {
            btnOpenAppeal.classList.remove("hidden");
            btnIssueCert.classList.add("hidden");
        }

        // Render Signals Grid
        signalsGrid.innerHTML = "";
        const signals = data.signals || {};
        for (const [key, sig] of Object.entries(signals)) {
            const card = document.createElement("div");
            card.className = "signal-card";

            const scorePct = Math.round(sig.ai_score * 100);
            let barColor = "#3b82f6";
            if (sig.ai_score >= 0.70) barColor = "#ef4444";
            else if (sig.ai_score <= 0.35) barColor = "#22c55e";
            else barColor = "#f59e0b";

            card.innerHTML = `
                <div class="signal-header">
                    <span>${sig.name}</span>
                    <span class="signal-weight">Weight: ${(sig.weight * 100).toFixed(0)}%</span>
                </div>
                <div class="signal-score-bar-bg">
                    <div class="signal-score-bar-fill" style="width: ${scorePct}%; background-color: ${barColor}"></div>
                </div>
                <div class="signal-desc">
                    <strong>Score:</strong> ${scorePct}% AI likelihood<br>
                    <strong>Reason:</strong> ${sig.reasoning || "Standard evaluation completed."}
                </div>
            `;
            signalsGrid.appendChild(card);
        }

        resultBox.scrollIntoView({ behavior: "smooth" });
    }

    function appendLogToTable(data, content) {
        const table = document.getElementById("audit-table").getElementsByTagName("tbody")[0];
        const noRec = document.getElementById("no-records-row");
        if (noRec) noRec.remove();

        const row = table.insertRow(0);
        const excerpt = content.length > 100 ? content.substring(0, 100) + "..." : content;
        const now = new Date().toISOString().substring(0, 19).replace("T", " ");

        row.innerHTML = `
            <td class="mono-text">${now}</td>
            <td class="mono-text"><a href="/submit/${data.submission_id}" target="_blank">${data.submission_id.substring(0, 8)}...</a></td>
            <td>${excerpt}</td>
            <td><span class="tag tag-${data.attribution}">${data.attribution.toUpperCase()}</span></td>
            <td><strong>${(data.confidence_score * 100).toFixed(1)}%</strong></td>
            <td class="mono-text text-sm">${data.label_variant}</td>
            <td><span class="status-pill status-active">active</span></td>
        `;
    }

    // Appeals Modal Actions
    btnOpenAppeal.addEventListener("click", () => {
        if (!currentSubmission) return;
        appealSubIdInput.value = currentSubmission.submission_id;
        appealCreatorInput.value = creatorInput.value || "creator_handle";
        appealReasoningInput.value = "";
        appealModal.classList.remove("hidden");
    });

    const closeModal = () => appealModal.classList.add("hidden");
    modalClose.addEventListener("click", closeModal);
    modalCancel.addEventListener("click", closeModal);

    appealForm.addEventListener("submit", async (e) => {
        e.preventDefault();
        const subId = appealSubIdInput.value;
        const creator = appealCreatorInput.value.trim();
        const reasoning = appealReasoningInput.value.trim();
        const assistance = appealAssistanceSelect.value;
        const evidence = appealEvidenceInput.value.trim();

        if (reasoning.length < 20) {
            alert("Reasoning must be at least 20 characters.");
            return;
        }

        try {
            const resp = await fetch("/appeal", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    submission_id: subId,
                    creator_id: creator,
                    reasoning: reasoning,
                    assistance_type: assistance,
                    supporting_evidence: evidence
                })
            });

            const data = await resp.json();
            if (!resp.ok) {
                alert(`Appeal submission error: ${data.error || data.message}`);
                return;
            }

            alert("Appeal successfully logged! Submission status changed to 'under_review'.");
            closeModal();
            window.location.reload();
        } catch (err) {
            alert(`Error filing appeal: ${err.message}`);
        }
    });

    // Provenance Certificate Action
    btnIssueCert.addEventListener("click", async () => {
        if (!currentSubmission) return;
        try {
            const resp = await fetch("/certificate/issue", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    submission_id: currentSubmission.submission_id,
                    creator_id: creatorInput.value || "verified_author",
                    verification_method: "draft_revision_history"
                })
            });

            const data = await resp.json();
            if (!resp.ok) {
                alert(`Error issuing certificate: ${data.error}`);
                return;
            }

            const cert = data.certificate;
            certBody.innerHTML = `
                <div style="text-align: center; padding: 20px 0;">
                    <div style="font-size: 3rem; margin-bottom: 12px;">🛡️</div>
                    <h2 style="color: #22c55e; margin-bottom: 8px;">Verified Human Origin</h2>
                    <p style="color: #94a3b8; font-size: 0.9rem; margin-bottom: 20px;">Issued by Provenance Guard Trust Network</p>
                    
                    <div style="background: #0d131d; padding: 16px; border-radius: 8px; text-align: left; font-family: monospace; font-size: 0.8rem; margin-bottom: 20px; border: 1px solid #233144;">
                        <div><strong>Certificate ID:</strong> ${cert.certificate_id}</div>
                        <div><strong>Creator ID:</strong> ${cert.creator_id}</div>
                        <div><strong>Issued At:</strong> ${cert.issued_at}</div>
                        <div><strong>Verification Hash:</strong> ${cert.verification_hash}</div>
                    </div>

                    <p style="font-size: 0.85rem; color: #cbd5e1; margin-bottom: 16px;">
                        Embeddable HTML badge for your creative platform:
                    </p>
                    <textarea class="form-control mono-box" rows="2" readonly>${cert.badge_markup}</textarea>
                </div>
            `;
            certModal.classList.remove("hidden");
        } catch (err) {
            alert(`Certificate error: ${err.message}`);
        }
    });

    certModalClose.addEventListener("click", () => certModal.classList.add("hidden"));

    // Appeals resolution button handler in table
    document.querySelectorAll(".btn-resolve").forEach(btn => {
        btn.addEventListener("click", async (e) => {
            const appealId = e.target.getAttribute("data-id");
            const newStatus = e.target.getAttribute("data-status");
            const notes = prompt(`Enter resolution notes for setting status to '${newStatus}':`, "Moderator verified authenticity.");
            if (notes === null) return;

            try {
                const resp = await fetch(`/appeal/${appealId}/resolve`, {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({ status: newStatus, reviewer_notes: notes })
                });
                if (resp.ok) {
                    alert(`Appeal marked as ${newStatus}.`);
                    window.location.reload();
                } else {
                    const err = await resp.json();
                    alert(`Resolution failed: ${err.error}`);
                }
            } catch (err) {
                alert(`Network error: ${err.message}`);
            }
        });
    });
});
