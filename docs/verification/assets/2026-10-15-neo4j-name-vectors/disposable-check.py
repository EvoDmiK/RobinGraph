"""Actual Neo4j 5.26 checks on the isolated, empty localhost QA container only.

Uses synthetic three-dimensional vectors and fixture taxa, not real TEST data.
"""
import json
import logging
from types import SimpleNamespace

from neo4j import GraphDatabase
from robingraph.graph.settings import Neo4jSettings
from robingraph.retrieval.taxon_name_vectors_neo4j import Neo4jTaxonNameVectorRepository

settings = Neo4jSettings('bolt://127.0.0.1:17687', 'qa', 'unused', 'neo4j')
logging.getLogger('neo4j.notifications').setLevel(logging.ERROR)
context = ('qa:concept', 'qa:release')
names = [dict(taxon_id='qa:a', scientific_name='Ardea cinerea', display_name='왜가리', text='왜가리'),
         dict(taxon_id='qa:b', scientific_name='Ardea alba', display_name='중대백로', text='중대백로')]


class Embeddings:
    profile = SimpleNamespace(model='qa-fixture', dimensions=3, normalized=True)

    def __init__(self):
        self.calls = []
        self.fail = False

    def embed_documents(self, texts):
        self.calls.append(list(texts))
        if self.fail:
            raise RuntimeError('injected fixture embedding failure')
        return [(1., 0., 0.) if text.startswith('왜') else (0., 1., 0.) for text in texts]


with GraphDatabase.driver(settings.uri, auth=('qa', 'unused')) as driver:
    with driver.session() as session:
        # Refuse to write an existing application DB, even if this QA port was reused.
        assert session.run('MATCH(n) RETURN count(n) AS n').single()['n'] == 0
        session.run("CREATE (:TaxonConceptSet {id:'qa:concept',version:'qa:release',policy_status:'allowed',dataset_id:'qa'})").consume()
        session.run("""UNWIND $names AS row MATCH(s:TaxonConceptSet {id:'qa:concept'})
            CREATE(t:Taxon:BirdTaxon {id:row.taxon_id,scientific_name:row.scientific_name,
              rank:'species',source_release:'qa:release',policy_status:'allowed',dataset_id:'qa'})
            CREATE(t)-[:IN_CONCEPT_SET]->(s)""", names=names).consume()
        session.run("CREATE VECTOR INDEX robingraphFixtureChunkVector FOR(n:HybridVectorChunk) ON(n.hybrid_vector) OPTIONS {indexConfig:{`vector.dimensions`:3,`vector.similarity_function`:'cosine'}}").consume()
        index_query = "SHOW INDEXES YIELD name,type,labelsOrTypes,properties,options WHERE name='robingraphFixtureChunkVector' RETURN name,type,labelsOrTypes,properties,options"
        literature_before = session.run(index_query).data()
        taxa_before = session.run('MATCH(t:Taxon) RETURN properties(t) AS properties ORDER BY t.id').data()
        assert session.run('MATCH(n:IngestState) RETURN count(n) AS n').single()['n'] == 0
    embedding = Embeddings()
    with Neo4jTaxonNameVectorRepository(settings) as repo:
        plan = repo.index_names(names, embedding, context)
        assert plan['to_embed'] == 2 and not embedding.calls
        first = repo.index_names(names, embedding, context, dry_run=False)
        assert first['embedded'] == 2
        hits = repo.search([1., 0., 0.], embedding.profile, context, names)
        assert hits[0]['taxon_id'] == 'qa:a' and abs(hits[0]['score'] - 1.) < 1e-6
        assert abs(next(h['score'] for h in hits if h['taxon_id'] == 'qa:b')) < 1e-6
        second = repo.index_names(names, embedding, context, dry_run=False)
        assert second['embedded'] == 0 and second['reused'] == 2 and len(embedding.calls) == 1
        changed = [{**names[0], 'text': '왜가리 갱신', 'display_name': '왜가리 갱신'}]
        embedding.fail = True
        try:
            repo.index_names(changed, embedding, context, dry_run=False)
            raise AssertionError('Expected embedding failure')
        except RuntimeError:
            pass
        assert len(repo.search([1., 0., 0.], embedding.profile, context, names)) == 2
        embedding.fail = False
        updated = repo.index_names(changed, embedding, context, dry_run=False)
        assert updated['embedded'] == 1 and updated['stale'] == 1
        assert [h['taxon_id'] for h in repo.search([1., 0., 0.], embedding.profile, context, changed)] == ['qa:a']
        try:
            repo.index_names(names, SimpleNamespace(profile=SimpleNamespace(model='wrong', dimensions=4, normalized=True)), context, dry_run=False)
            raise AssertionError('Expected dimension mismatch')
        except ValueError:
            pass
    # A new repository/process connection uses persisted vectors without a model.
    with Neo4jTaxonNameVectorRepository(settings) as repo:
        assert repo.search([1., 0., 0.], embedding.profile, context, changed)[0]['taxon_id'] == 'qa:a'
    with driver.session() as session:
        assert session.run(index_query).data() == literature_before
        assert session.run('MATCH(t:Taxon) RETURN properties(t) AS properties ORDER BY t.id').data() == taxa_before
        score = session.run('RETURN vector.similarity.cosine([1.0,0.0],[0.0,1.0]) AS score').single()['score']
        assert score == .5

print(json.dumps({'passed': True, 'mode': 'actual isolated Neo4j5.26.30, fixture taxa and vectors, no shared TEST writes',
                  'dry_run': plan, 'first_apply': first, 'idempotent_apply': second, 'changed_apply': updated,
                  'score_conversion': True, 'failure_preserves_old_catalog': True,
                  'fresh_repository_reuses_vectors': True, 'literature_index_unchanged': True,
                  'taxa_unchanged': True, 'no_legacy_ingest_state': True}, indent=2))
