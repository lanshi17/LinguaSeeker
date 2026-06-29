/* Embedded responsive styles for BilingualEvidenceView and its sub-components */

export const bevEmbeddedCSS = `
.bev-main-grid {
  display: grid;
  gap: 20px;
}
@media (min-width: 1024px) {
  .bev-main-grid {
    grid-template-columns: 280px minmax(0, 1fr);
  }
}
.bev-bilingual-grid {
  display: grid;
  gap: 16px;
}
.bev-literature-header-content {
  flex-wrap: wrap;
}
@media (min-width: 640px) {
  .bev-literature-header-content {
    flex-wrap: nowrap;
  }
}
@media (min-width: 1024px) {
  .bev-bilingual-grid.bev-bilingual-grid--dual {
    grid-template-columns: 1fr 1fr;
  }
}
.bev-link:hover {
  color: #4b5563;
}
.bev-pmid-link:hover {
  color: var(--color-primary-700);
}
.bev-eye-btn:hover {
  color: #4b5563;
  background-color: #f3f4f6;
}
.bev-nav-item:hover {
  background-color: #f9fafb;
}
.bev-nav-item--selected {
  background-color: var(--color-primary-50);
  border: 1px solid var(--color-primary-200);
}
`;
