"""Explicitly scoped audio collection sidecar; publication and public media routes do not exist."""
import os
from pathlib import Path

from django.urls import path
from rest_framework.response import Response

from robingraph.api.drf.application import DjangoApiApplication, configure_default_settings
configure_default_settings()

from robingraph.api.drf.audio_views import AudioOperationView, AudioMediaView
from robingraph.api.drf.urls import UrlConf
from robingraph.api.drf.views import RobinGraphView, threaded
from robingraph.api.services import ApiError
from robingraph.graph.settings import Neo4jSettings
from robingraph.ingest.postgres import PostgresSettings
from robingraph.retrieval.species_scope import distribution_for
from robingraph.retrieval.taxonomy_lineage_neo4j import Neo4jTaxonomyLineageRepository
from .audio import AudioService
from .audio_store import AudioStore


class CollectorHealthView(RobinGraphView):
    http_method_names=['get','head']
    target=None

    def get(self,request):
        return Response({'status':'ok','service':'audio-collector','deployment_target':self.target,
                         'publication_enabled':False})

    head=get


def create_app(audio_service,target):
    if target not in ('test','prod'):
        raise ValueError('An explicit test or prod collector target is required')
    configure_default_settings()
    patterns=[path('health',threaded(CollectorHealthView.as_view(target=target))),
              path('internal/v1/audio/preview/<str:name>',threaded(AudioMediaView.as_view(audio=audio_service,private=True)))]
    for action in ('targets','discover','stage','status','review'):
        patterns.append(path('internal/v1/audio/'+action,
                             threaded(AudioOperationView.as_view(audio=audio_service)),kwargs={'action':action}))
    return DjangoApiApplication(UrlConf(patterns),{'openapi':'3.1.0','paths':{}})


def validate_target(environ,pg,neo):
    target=environ.get('ROBINGRAPH_DEPLOY_TARGET')
    if environ.get('ROBINGRAPH_AUDIO_COLLECTOR_ENABLED')!='true' or target not in ('test','prod'):
        raise ValueError('Audio collector requires an explicit enabled deployment target')
    expected_database='robingraph' if target=='prod' else 'robingraph_test'
    expected_neo4j='bolt://neo4j:7687' if target=='prod' else 'bolt://192.168.219.98:7687'
    if (pg.host,pg.port,pg.database,pg.schema)!=('192.168.219.99',5433,expected_database,'ingest'):
        raise ValueError('Audio collector PostgreSQL target differs from the confirmed environment')
    if (neo.uri,neo.database)!=(expected_neo4j,'neo4j'):
        raise ValueError('Audio collector graph target differs from the confirmed environment')
    root=environ.get('ROBINGRAPH_AUDIO_ROOT','')
    if not root or not Path(root).is_absolute() or not Path(root).is_dir() or not os.access(root,os.W_OK):
        raise ValueError('Audio collector requires an existing writable persistent audio directory')
    if not environ.get('ROBINGRAPH_INGEST_INTERNAL_TOKEN'):
        raise ValueError('Audio collector requires the internal bearer token')
    return target


def create_from_environment():
    pg=PostgresSettings.from_environment();neo=Neo4jSettings.from_environment()
    target=validate_target(os.environ,pg,neo)
    store=AudioStore(pg)

    def active_context():
        context=store.active_release_context('reference-taxonomy-traits')
        cursor=context.cursor if context is not None else {}
        concept=cursor.get('concept_set_id',cursor.get('taxonomy_concept_set_id'))
        release=cursor.get('taxonomy_release')
        return (concept,release) if isinstance(concept,str) and isinstance(release,str) else None

    if active_context() is None:
        raise ValueError('Audio collector requires an active reference taxonomy')
    repository=Neo4jTaxonomyLineageRepository(neo,active_taxonomy_context=active_context)

    def exact_species(scientific_name):
        lineage=repository.lineage_for_scientific_name(scientific_name)
        if lineage is None or lineage.items[-1].rank!='species' or lineage.items[-1].scientific_name!=scientific_name:
            raise ApiError(422,'A unique active exact species is required')
        item=lineage.items[-1]
        if distribution_for({'taxon_id':item.taxon_id,'scientific_name':scientific_name,'rank':item.rank},
                            lineage.concept_set_id,lineage.taxonomy_release)['status']!='korea':
            raise ApiError(422,'A reviewed Korean wild-record scope is required')
        return {'taxon_id':item.taxon_id,'concept_set_id':lineage.concept_set_id,
                'taxonomy_release':lineage.taxonomy_release}

    service=AudioService(store,os.environ['ROBINGRAPH_AUDIO_ROOT'],repository,exact_species,
                         os.environ['ROBINGRAPH_INGEST_INTERNAL_TOKEN'])
    app=create_app(service,target)
    app.collector_repository=repository
    return app


def main():
    import uvicorn
    app=create_from_environment()
    try:
        uvicorn.run(app,host='0.0.0.0',port=8000)
    finally:
        app.collector_repository.close()


if __name__=='__main__':
    main()
