export const state = {
  projects: [],
  project: null,
  results: {},
  library: [],
  settings: null,
}

export function setProject(project) {
  state.project = project
  state.results = {}
}

export function selectedSources() {
  return [...document.querySelectorAll(".source:checked")].map(x => x.value)
}
