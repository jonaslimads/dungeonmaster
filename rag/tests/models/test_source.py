from rag.models.source import Source


def test_source_creation():
    source = Source(
        id="dnd_5e_players_handbook",
        title="D&D 5E Player's Handbook",
        source_type="core_rulebook",
        system="dnd_5e",
        original_path="/app/data/rag/sources/dnd_5e_players_handbook/original/source.pdf",
        status="registered",
    )
    assert source.id == "dnd_5e_players_handbook"
    assert source.status == "registered"
    assert source.page_count is None


def test_source_with_page_count():
    source = Source(
        id="test",
        title="Test",
        source_type="test",
        system="test",
        original_path="/test.pdf",
        status="registered",
        page_count=330,
    )
    assert source.page_count == 330
