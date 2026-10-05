from pathlib import Path

from german_job_market.demo import render_page
from german_job_market.skills import load_taxonomy


def test_render_page_escapes_and_lists_skills() -> None:
    taxonomy = load_taxonomy(Path("configs/skill_taxonomy.toml"))
    page = render_page(taxonomy, None, "<script>x</script>")
    assert "&lt;script&gt;" in page and "<script>" not in page
    assert page.count('name="skill"') == len(taxonomy.skills)
