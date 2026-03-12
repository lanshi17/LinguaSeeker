-- Generated INSERT statements for ACMG database


INSERT INTO documents (id, original_filename, minio_path, status, pmid, doi, title, authors, journal, publication_year, created_at, updated_at) 
VALUES ('c3d8ae81-112c-4fd1-abf6-1d73ff5ea664', 'ACMG_Study_1173.pdf', 'documents/c3d8ae81/ACMG_Study_2785.pdf', 'parsing', '66407575', '10.1000/journal.v1.1', 'Clinical Utility of Multi-Gene Panel Testing for Hereditary Cancer', '["Linda Williams", "Patricia Smith", "Patricia Williams"]', 'BMC Medical Genetics', 2020, '2020-12-08 00:00:00', '2020-12-30 00:00:00')
ON CONFLICT (pmid) DO NOTHING;

INSERT INTO documents (id, original_filename, minio_path, status, pmid, doi, title, authors, journal, publication_year, created_at, updated_at) 
VALUES ('193e33fd-4913-4d7e-badf-49b1a73e9641', 'ACMG_Study_7335.pdf', 'documents/193e33fd/ACMG_Study_9052.pdf', 'parsing', '52863149', '10.1000/journal.v12.90', 'Clinical Utility of Multi-Gene Panel Testing for Hereditary Cancer', '["Mary Williams", "Mary Brown"]', 'Journal of Medical Genetics', 2022, '2022-05-16 00:00:00', '2022-05-24 00:00:00')
ON CONFLICT (pmid) DO NOTHING;

INSERT INTO documents (id, original_filename, minio_path, status, pmid, doi, title, authors, journal, publication_year, created_at, updated_at) 
VALUES ('bf2ecaaa-f46f-461b-897f-6976dd2e1565', 'ACMG_Study_2188.pdf', 'documents/bf2ecaaa/ACMG_Study_8242.pdf', 'parsing', '45046223', '10.1000/journal.v18.25', 'ACMG Recommendations for Variant Classification in Clinical Practice', '["James Brown", "Mary Jones", "Jennifer Smith", "Jennifer Jones", "Linda Jones"]', 'New England Journal of Medicine', 2024, '2024-05-13 00:00:00', '2024-05-19 00:00:00')
ON CONFLICT (pmid) DO NOTHING;

INSERT INTO documents (id, original_filename, minio_path, status, pmid, doi, title, authors, journal, publication_year, created_at, updated_at) 
VALUES ('a2aedd41-a6fc-450a-8275-add28a1d156b', 'ACMG_Study_8669.pdf', 'documents/a2aedd41/ACMG_Study_6649.pdf', 'parsing', '31687925', '10.1000/journal.v5.5', 'Novel Variants in BRCA1 Associated with Hereditary Breast Cancer', '["Mary Rodriguez", "Patricia Martinez"]', 'Journal of Medical Genetics', 2023, '2023-12-22 00:00:00', '2024-01-21 00:00:00')
ON CONFLICT (pmid) DO NOTHING;

INSERT INTO documents (id, original_filename, minio_path, status, pmid, doi, title, authors, journal, publication_year, created_at, updated_at) 
VALUES ('47e1f687-abee-436e-b798-09eb876f76ac', 'ACMG_Study_5000.pdf', 'documents/47e1f687/ACMG_Study_2080.pdf', 'completed', '64696670', '10.1000/journal.v9.3', 'ACMG Recommendations for Variant Classification in Clinical Practice', '["Patricia Martinez", "Mary Brown", "Robert Williams", "Linda Davis", "Michael Martinez"]', 'Clinical Genetics', 2023, '2023-04-06 00:00:00', '2023-04-29 00:00:00')
ON CONFLICT (pmid) DO NOTHING;

INSERT INTO documents (id, original_filename, minio_path, status, pmid, doi, title, authors, journal, publication_year, created_at, updated_at) 
VALUES ('76874fc1-2833-4af7-aa80-29bab2d134b6', 'ACMG_Study_2856.pdf', 'documents/76874fc1/ACMG_Study_6661.pdf', 'completed', '74839077', '10.1000/journal.v13.15', 'Functional Validation of Uncertain Significance Variants in COL1A1', '["Jennifer Rodriguez", "Michael Johnson", "John Miller", "Patricia Rodriguez", "James Brown", "Jennifer Rodriguez"]', 'Genetics in Medicine', 2022, '2022-01-27 00:00:00', '2022-02-23 00:00:00')
ON CONFLICT (pmid) DO NOTHING;

INSERT INTO documents (id, original_filename, minio_path, status, pmid, doi, title, authors, journal, publication_year, created_at, updated_at) 
VALUES ('45cc4067-057c-43ab-8207-c3fc5004c960', 'ACMG_Study_2048.pdf', 'documents/45cc4067/ACMG_Study_5446.pdf', 'failed', '64682841', '10.1000/journal.v9.29', 'Population-Specific Allele Frequencies in Genetic Disease Screening', '["Patricia Williams", "Mary Martinez", "Michael Miller"]', 'Clinical Genetics', 2020, '2020-10-10 00:00:00', '2020-10-17 00:00:00')
ON CONFLICT (pmid) DO NOTHING;

INSERT INTO documents (id, original_filename, minio_path, status, pmid, doi, title, authors, journal, publication_year, created_at, updated_at) 
VALUES ('b221b811-166a-4c90-a8cf-d7614ff50a02', 'ACMG_Study_5423.pdf', 'documents/b221b811/ACMG_Study_9838.pdf', 'parsing', '34913951', '10.1000/journal.v4.81', 'Functional Validation of Uncertain Significance Variants in COL1A1', '["Robert Smith"]', 'BMC Medical Genetics', 2020, '2020-03-06 00:00:00', '2020-03-23 00:00:00')
ON CONFLICT (pmid) DO NOTHING;

INSERT INTO documents (id, original_filename, minio_path, status, pmid, doi, title, authors, journal, publication_year, created_at, updated_at) 
VALUES ('83d52161-c973-43a4-8bf1-50e3bf91b4c0', 'ACMG_Study_5140.pdf', 'documents/83d52161/ACMG_Study_2082.pdf', 'parsing', '98424413', '10.1000/journal.v4.77', 'Genetic Analysis of Lynch Syndrome Families', '["James Rodriguez", "William Rodriguez", "James Johnson", "Elizabeth Smith"]', 'Human Mutation', 2024, '2024-10-15 00:00:00', '2024-10-20 00:00:00')
ON CONFLICT (pmid) DO NOTHING;

INSERT INTO documents (id, original_filename, minio_path, status, pmid, doi, title, authors, journal, publication_year, created_at, updated_at) 
VALUES ('2deb31c1-2992-4ef6-82a6-6418f1d97a47', 'ACMG_Study_3255.pdf', 'documents/2deb31c1/ACMG_Study_2405.pdf', 'uploaded', '10018050', '10.1000/journal.v9.38', 'Genetic Analysis of Lynch Syndrome Families', '["John Williams", "Robert Williams", "Linda Martinez"]', 'European Journal of Human Genetics', 2023, '2023-10-06 00:00:00', '2023-11-05 00:00:00')
ON CONFLICT (pmid) DO NOTHING;

INSERT INTO documents (id, original_filename, minio_path, status, pmid, doi, title, authors, journal, publication_year, created_at, updated_at) 
VALUES ('c56bc782-12ed-4aa0-ad19-d25982bd284e', 'ACMG_Study_4322.pdf', 'documents/c56bc782/ACMG_Study_8330.pdf', 'parsing', '78764066', '10.1000/journal.v13.81', 'Novel Variants in BRCA1 Associated with Hereditary Breast Cancer', '["James Brown", "James Jones", "Patricia Jones", "William Johnson", "Elizabeth Williams", "James Williams"]', 'Nature Genetics', 2022, '2022-01-06 00:00:00', '2022-01-29 00:00:00')
ON CONFLICT (pmid) DO NOTHING;

INSERT INTO documents (id, original_filename, minio_path, status, pmid, doi, title, authors, journal, publication_year, created_at, updated_at) 
VALUES ('ca653959-af55-4ee4-bc5b-2509e40b26b8', 'ACMG_Study_3474.pdf', 'documents/ca653959/ACMG_Study_1559.pdf', 'parsing', '94377417', '10.1000/journal.v11.30', 'Systematic Review of Genetic Testing Guidelines for Rare Diseases', '["Jennifer Davis", "John Davis", "Patricia Brown", "Mary Rodriguez", "Patricia Martinez"]', 'New England Journal of Medicine', 2022, '2022-05-14 00:00:00', '2022-05-16 00:00:00')
ON CONFLICT (pmid) DO NOTHING;

INSERT INTO documents (id, original_filename, minio_path, status, pmid, doi, title, authors, journal, publication_year, created_at, updated_at) 
VALUES ('91f76c8f-ba40-47f5-b804-f1bd9fafdbe1', 'ACMG_Study_3870.pdf', 'documents/91f76c8f/ACMG_Study_1349.pdf', 'completed', '50821259', '10.1000/journal.v18.31', 'Genetic Analysis of Lynch Syndrome Families', '["Jennifer Williams", "Mary Brown", "Linda Miller"]', 'BMC Medical Genetics', 2024, '2024-11-27 00:00:00', '2024-12-09 00:00:00')
ON CONFLICT (pmid) DO NOTHING;

INSERT INTO documents (id, original_filename, minio_path, status, pmid, doi, title, authors, journal, publication_year, created_at, updated_at) 
VALUES ('92ecac31-f768-4daf-aafc-b2f8d860900c', 'ACMG_Study_9631.pdf', 'documents/92ecac31/ACMG_Study_4557.pdf', 'failed', '93005677', '10.1000/journal.v9.81', 'Evidence-Based Approach to ACMG Secondary Findings Implementation', '["Robert Miller", "Mary Williams"]', 'New England Journal of Medicine', 2021, '2021-11-28 00:00:00', '2021-11-29 00:00:00')
ON CONFLICT (pmid) DO NOTHING;

INSERT INTO documents (id, original_filename, minio_path, status, pmid, doi, title, authors, journal, publication_year, created_at, updated_at) 
VALUES ('36e30111-098d-4c89-a978-65b3845b506e', 'ACMG_Study_8810.pdf', 'documents/36e30111/ACMG_Study_6523.pdf', 'failed', '44014566', '10.1000/journal.v2.82', 'Population-Specific Allele Frequencies in Genetic Disease Screening', '["Elizabeth Johnson", "Michael Williams", "Jennifer Davis", "Mary Johnson"]', 'Genetic Medicine', 2023, '2023-07-12 00:00:00', '2023-07-22 00:00:00')
ON CONFLICT (pmid) DO NOTHING;

INSERT INTO documents (id, original_filename, minio_path, status, pmid, doi, title, authors, journal, publication_year, created_at, updated_at) 
VALUES ('bfb28449-cc13-4ac4-bf98-17e6a0d2cc9e', 'ACMG_Study_8403.pdf', 'documents/bfb28449/ACMG_Study_3194.pdf', 'uploaded', '80511652', '10.1000/journal.v7.30', 'Clinical Utility of Multi-Gene Panel Testing for Hereditary Cancer', '["Jennifer Miller"]', 'Journal of Medical Genetics', 2020, '2020-12-11 00:00:00', '2020-12-15 00:00:00')
ON CONFLICT (pmid) DO NOTHING;

INSERT INTO documents (id, original_filename, minio_path, status, pmid, doi, title, authors, journal, publication_year, created_at, updated_at) 
VALUES ('0c9b6fd1-3f5d-47ac-883a-cd21ce5a02b6', 'ACMG_Study_3287.pdf', 'documents/0c9b6fd1/ACMG_Study_2757.pdf', 'completed', '86655524', '10.1000/journal.v17.38', 'Novel Variants in BRCA1 Associated with Hereditary Breast Cancer', '["Linda Brown", "Patricia Smith", "James Rodriguez"]', 'Nature Genetics', 2020, '2020-03-01 00:00:00', '2020-03-16 00:00:00')
ON CONFLICT (pmid) DO NOTHING;

INSERT INTO documents (id, original_filename, minio_path, status, pmid, doi, title, authors, journal, publication_year, created_at, updated_at) 
VALUES ('f525a3d4-2690-49b6-ac1a-c0b39a47faec', 'ACMG_Study_3061.pdf', 'documents/f525a3d4/ACMG_Study_1294.pdf', 'uploaded', '76411956', '10.1000/journal.v16.52', 'Genetic Analysis of Lynch Syndrome Families', '["Elizabeth Martinez", "John Brown", "Mary Rodriguez", "Michael Williams"]', 'American Journal of Human Genetics', 2022, '2022-03-05 00:00:00', '2022-03-30 00:00:00')
ON CONFLICT (pmid) DO NOTHING;

INSERT INTO documents (id, original_filename, minio_path, status, pmid, doi, title, authors, journal, publication_year, created_at, updated_at) 
VALUES ('ca2fd067-0f87-4d28-b59a-9ff07eb92f10', 'ACMG_Study_3117.pdf', 'documents/ca2fd067/ACMG_Study_8874.pdf', 'completed', '32079034', '10.1000/journal.v17.9', 'Genetic Analysis of Lynch Syndrome Families', '["Elizabeth Rodriguez"]', 'European Journal of Human Genetics', 2023, '2023-02-27 00:00:00', '2023-03-12 00:00:00')
ON CONFLICT (pmid) DO NOTHING;

INSERT INTO documents (id, original_filename, minio_path, status, pmid, doi, title, authors, journal, publication_year, created_at, updated_at) 
VALUES ('8be9310a-fa84-48e7-8212-3dfce053f8b6', 'ACMG_Study_9779.pdf', 'documents/8be9310a/ACMG_Study_8115.pdf', 'parsing', '84341365', '10.1000/journal.v3.51', 'ACMG Recommendations for Variant Classification in Clinical Practice', '["James Williams"]', 'Journal of Medical Genetics', 2024, '2024-02-14 00:00:00', '2024-03-01 00:00:00')
ON CONFLICT (pmid) DO NOTHING;

INSERT INTO parsing_tasks (id, document_id, task_type, celery_task_id, result_path, status, progress, error_message, created_at, completed_at) 
VALUES ('6eafb0ff-bcbc-4251-9303-e7c0ac81e4ec', 'c3d8ae81-112c-4fd1-abf6-1d73ff5ea664', 'identifier_resolve', 'task-7bb1f415-6596-462e-8d50-870cb4bcd496', 'results/6eafb0ff/parsed_data.json', 'processing', 32, NULL, '2020-12-08 20:00:00', '2020-12-08 21:09:00')
ON CONFLICT (id) DO NOTHING;

INSERT INTO parsing_tasks (id, document_id, task_type, celery_task_id, result_path, status, progress, error_message, created_at, completed_at) 
VALUES ('456981fc-eac4-41a6-867a-12a5f1e9059e', '193e33fd-4913-4d7e-badf-49b1a73e9641', 'identifier_resolve', 'task-c71a3232-ae2d-4e5a-9274-da4fd8c4851d', 'results/456981fc/parsed_data.json', 'completed', 71, NULL, '2022-05-16 09:00:00', '2022-05-16 10:27:00')
ON CONFLICT (id) DO NOTHING;

INSERT INTO parsing_tasks (id, document_id, task_type, celery_task_id, result_path, status, progress, error_message, created_at, completed_at) 
VALUES ('718ffc96-293d-4814-9c26-d1a92987b84e', 'bf2ecaaa-f46f-461b-897f-6976dd2e1565', 'pdf_parse', 'task-4ab89520-6f21-44af-8c59-f93041e02d3c', 'results/718ffc96/parsed_data.json', 'completed', 85, NULL, '2024-05-13 04:00:00', '2024-05-13 05:26:00')
ON CONFLICT (id) DO NOTHING;

INSERT INTO parsing_tasks (id, document_id, task_type, celery_task_id, result_path, status, progress, error_message, created_at, completed_at) 
VALUES ('29298603-2469-4ebb-bb9f-211025ff7673', 'a2aedd41-a6fc-450a-8275-add28a1d156b', 'identifier_resolve', 'task-b1984d3a-7b69-44e8-87e5-f2b368ad0d7f', 'results/29298603/parsed_data.json', 'completed', 52, NULL, '2023-12-22 05:00:00', '2023-12-22 05:26:00')
ON CONFLICT (id) DO NOTHING;

INSERT INTO parsing_tasks (id, document_id, task_type, celery_task_id, result_path, status, progress, error_message, created_at, completed_at) 
VALUES ('6c64ebd5-3050-49da-8689-de1f7627f15f', '47e1f687-abee-436e-b798-09eb876f76ac', 'identifier_resolve', 'task-344c04ea-2e7e-4c88-9437-1c823a87e505', 'results/6c64ebd5/parsed_data.json', 'failed', 95, NULL, '2023-04-06 15:00:00', '2023-04-06 15:40:00')
ON CONFLICT (id) DO NOTHING;

INSERT INTO parsing_tasks (id, document_id, task_type, celery_task_id, result_path, status, progress, error_message, created_at, completed_at) 
VALUES ('cff52dbf-c2f4-4087-94f2-85669572951e', '76874fc1-2833-4af7-aa80-29bab2d134b6', 'pdf_parse', 'task-cccbbc61-26c6-4e8a-95ff-0c5d95601084', 'results/cff52dbf/parsed_data.json', 'completed', 22, NULL, '2022-01-27 08:00:00', '2022-01-27 09:34:00')
ON CONFLICT (id) DO NOTHING;

INSERT INTO parsing_tasks (id, document_id, task_type, celery_task_id, result_path, status, progress, error_message, created_at, completed_at) 
VALUES ('64442813-0bf1-448d-b8b9-eae96ead9985', '45cc4067-057c-43ab-8207-c3fc5004c960', 'identifier_resolve', 'task-4d7f51c6-bd04-4791-8936-a7de321a9bd2', 'results/64442813/parsed_data.json', 'completed', 89, NULL, '2020-10-10 11:00:00', '2020-10-10 12:28:00')
ON CONFLICT (id) DO NOTHING;

INSERT INTO parsing_tasks (id, document_id, task_type, celery_task_id, result_path, status, progress, error_message, created_at, completed_at) 
VALUES ('a93ca233-3beb-4c8e-9cfe-2f42cf100584', 'b221b811-166a-4c90-a8cf-d7614ff50a02', 'identifier_resolve', 'task-e7ac5b45-8707-46ab-b9d4-8b18d69278fe', 'results/a93ca233/parsed_data.json', 'failed', 6, NULL, '2020-03-06 18:00:00', '2020-03-06 19:53:00')
ON CONFLICT (id) DO NOTHING;

INSERT INTO parsing_tasks (id, document_id, task_type, celery_task_id, result_path, status, progress, error_message, created_at, completed_at) 
VALUES ('5af78757-1202-4597-a883-9471fa67535d', '83d52161-c973-43a4-8bf1-50e3bf91b4c0', 'pdf_parse', 'task-c45db69b-3bee-4848-b84b-c36747cd0c10', 'results/5af78757/parsed_data.json', 'completed', 3, NULL, '2024-10-15 05:00:00', '2024-10-15 06:29:00')
ON CONFLICT (id) DO NOTHING;

INSERT INTO parsing_tasks (id, document_id, task_type, celery_task_id, result_path, status, progress, error_message, created_at, completed_at) 
VALUES ('1124605c-13b3-4a4d-bcac-c06e55f97d3c', '2deb31c1-2992-4ef6-82a6-6418f1d97a47', 'pdf_parse', 'task-ba131979-41c4-4309-aae5-4ecb7e30aea8', 'results/1124605c/parsed_data.json', 'completed', 78, NULL, '2023-10-06 05:00:00', NULL)
ON CONFLICT (id) DO NOTHING;

INSERT INTO parsing_tasks (id, document_id, task_type, celery_task_id, result_path, status, progress, error_message, created_at, completed_at) 
VALUES ('68ab36ba-d68c-45ae-a2e8-b037cea66ecd', 'c56bc782-12ed-4aa0-ad19-d25982bd284e', 'identifier_resolve', 'task-efc66292-9ff1-470d-bf66-3e201157c2b9', 'results/68ab36ba/parsed_data.json', 'pending', 93, NULL, '2022-01-06 06:00:00', NULL)
ON CONFLICT (id) DO NOTHING;

INSERT INTO parsing_tasks (id, document_id, task_type, celery_task_id, result_path, status, progress, error_message, created_at, completed_at) 
VALUES ('47909f2d-d203-4caa-a952-217abe5e229b', 'ca653959-af55-4ee4-bc5b-2509e40b26b8', 'identifier_resolve', 'task-8bbcc94d-e57e-4882-8d2e-54d65ed566fb', 'results/47909f2d/parsed_data.json', 'completed', 55, NULL, '2022-05-14 17:00:00', '2022-05-14 18:51:00')
ON CONFLICT (id) DO NOTHING;

INSERT INTO parsing_tasks (id, document_id, task_type, celery_task_id, result_path, status, progress, error_message, created_at, completed_at) 
VALUES ('fa9213de-c90d-47ef-8198-d18aa1b0cfaa', '91f76c8f-ba40-47f5-b804-f1bd9fafdbe1', 'identifier_resolve', 'task-acedf489-5f16-489f-ae83-f62aa9a58d15', 'results/fa9213de/parsed_data.json', 'failed', 79, NULL, '2024-11-27 02:00:00', '2024-11-27 03:58:00')
ON CONFLICT (id) DO NOTHING;

INSERT INTO parsing_tasks (id, document_id, task_type, celery_task_id, result_path, status, progress, error_message, created_at, completed_at) 
VALUES ('ca481507-eec3-4c7d-8ca7-5f8dc0518981', '92ecac31-f768-4daf-aafc-b2f8d860900c', 'pdf_parse', 'task-43948d1c-2295-4fc2-bfb4-1e00fb807dd1', 'results/ca481507/parsed_data.json', 'processing', 47, NULL, '2021-11-28 05:00:00', '2021-11-28 05:23:00')
ON CONFLICT (id) DO NOTHING;

INSERT INTO parsing_tasks (id, document_id, task_type, celery_task_id, result_path, status, progress, error_message, created_at, completed_at) 
VALUES ('f1114ac9-13be-488e-8fa3-eced1e2eaa4f', '36e30111-098d-4c89-a978-65b3845b506e', 'identifier_resolve', 'task-5d4d882c-f0f3-4dc2-8475-d745a3bed433', 'results/f1114ac9/parsed_data.json', 'processing', 54, 'Gene-specific Case-control Statistical Segregation Literature Clinical.', '2023-07-12 15:00:00', '2023-07-12 16:07:00')
ON CONFLICT (id) DO NOTHING;

INSERT INTO parsing_tasks (id, document_id, task_type, celery_task_id, result_path, status, progress, error_message, created_at, completed_at) 
VALUES ('a0273e1c-2dc6-483f-a4a9-259203365a9c', 'bfb28449-cc13-4ac4-bf98-17e6a0d2cc9e', 'identifier_resolve', 'task-81442596-0673-4f8e-b3e4-a8b5ee756d37', 'results/a0273e1c/parsed_data.json', 'failed', 48, NULL, '2020-12-11 01:00:00', '2020-12-11 01:50:00')
ON CONFLICT (id) DO NOTHING;

INSERT INTO parsing_tasks (id, document_id, task_type, celery_task_id, result_path, status, progress, error_message, created_at, completed_at) 
VALUES ('e7472f56-326e-4bd2-b23c-17fb2cb9b034', '0c9b6fd1-3f5d-47ac-883a-cd21ce5a02b6', 'pdf_parse', 'task-3ddf83fe-ffb4-4b0b-ba52-3fa45897963e', 'results/e7472f56/parsed_data.json', 'pending', 76, NULL, '2020-03-01 14:00:00', '2020-03-01 14:40:00')
ON CONFLICT (id) DO NOTHING;

INSERT INTO parsing_tasks (id, document_id, task_type, celery_task_id, result_path, status, progress, error_message, created_at, completed_at) 
VALUES ('65f4bac4-6115-4c05-9732-fe5a2e181956', 'f525a3d4-2690-49b6-ac1a-c0b39a47faec', 'identifier_resolve', 'task-1699bf1d-6d90-4a20-81bd-29f253fb30ce', 'results/65f4bac4/parsed_data.json', 'processing', 38, NULL, '2022-03-05 09:00:00', NULL)
ON CONFLICT (id) DO NOTHING;

INSERT INTO parsing_tasks (id, document_id, task_type, celery_task_id, result_path, status, progress, error_message, created_at, completed_at) 
VALUES ('3cf42a0d-a040-4ffe-b0a7-73dae1bcd54f', 'ca2fd067-0f87-4d28-b59a-9ff07eb92f10', 'identifier_resolve', 'task-3a3ca223-a3ee-472e-a531-e82439b29cd8', 'results/3cf42a0d/parsed_data.json', 'pending', 55, 'Gene-specific Clinical The Segregation Literature Segregation.', '2023-02-27 23:00:00', '2023-02-27 23:10:00')
ON CONFLICT (id) DO NOTHING;

INSERT INTO parsing_tasks (id, document_id, task_type, celery_task_id, result_path, status, progress, error_message, created_at, completed_at) 
VALUES ('8291b44c-1738-46bc-8b5a-006384fa6957', '8be9310a-fa84-48e7-8212-3dfce053f8b6', 'identifier_resolve', 'task-33107efd-de75-4fee-8f97-c9d43afe82e7', 'results/8291b44c/parsed_data.json', 'failed', 42, NULL, '2024-02-14 07:00:00', NULL)
ON CONFLICT (id) DO NOTHING;

INSERT INTO evidence_records (id, document_id, evidence_type, content, confidence_score, source_page, source_position, status, neo4j_node_id, created_at, reviewed_by, reviewed_at) 
VALUES ('55b0c751-ccac-4030-be52-48291480223d', 'c3d8ae81-112c-4fd1-abf6-1d73ff5ea664', 'PM4', 'Segregation Gene-specific Statistical Segregation Gene-specific Statistical The Segregation Segregation Segregation Segregation Literature.', 0.53, 42, 'Page 5, Column Left', 'approved', 'node_5170', '2020-12-19 00:00:00', NULL, '2020-12-25 00:00:00')
ON CONFLICT (id) DO NOTHING;

INSERT INTO evidence_records (id, document_id, evidence_type, content, confidence_score, source_page, source_position, status, neo4j_node_id, created_at, reviewed_by, reviewed_at) 
VALUES ('e6e09aab-cbcd-4f68-89c9-52d768984ff6', 'c3d8ae81-112c-4fd1-abf6-1d73ff5ea664', 'BP1', 'Family Functional Functional Case-control Clinical The Literature Functional Literature Statistical Computational Clinical.', 0.91, 12, 'Page 40, Column Right', 'approved', 'node_1238', '2020-12-31 00:00:00', 'b09ada30-0f4d-469b-bf3f-32d9b10d3145', '2021-01-01 00:00:00')
ON CONFLICT (id) DO NOTHING;

INSERT INTO evidence_records (id, document_id, evidence_type, content, confidence_score, source_page, source_position, status, neo4j_node_id, created_at, reviewed_by, reviewed_at) 
VALUES ('adcfa2b1-3af8-4865-81fb-e52905d08d42', 'c3d8ae81-112c-4fd1-abf6-1d73ff5ea664', 'BS2', 'Computational Gene-specific Segregation Clinical Segregation Segregation Functional Case-control Computational Literature Literature Computational.', 0.59, 8, 'Page 46, Column Left', 'rejected', 'node_6063', '2020-12-10 00:00:00', 'ba775c30-c3d0-4c79-b462-259c495b7efd', NULL)
ON CONFLICT (id) DO NOTHING;

INSERT INTO evidence_records (id, document_id, evidence_type, content, confidence_score, source_page, source_position, status, neo4j_node_id, created_at, reviewed_by, reviewed_at) 
VALUES ('ed20a616-fb19-4beb-88da-e9e0b51ab812', 'c3d8ae81-112c-4fd1-abf6-1d73ff5ea664', 'PP1', 'Computational Gene-specific Gene-specific The Segregation Computational Literature Computational Gene-specific Functional The Computational.', 0.88, 24, 'Page 29, Column Right', 'approved', 'node_4977', '2020-12-23 00:00:00', 'e07e2d3d-3151-445b-84b8-8feb45a37c1b', NULL)
ON CONFLICT (id) DO NOTHING;

INSERT INTO evidence_records (id, document_id, evidence_type, content, confidence_score, source_page, source_position, status, neo4j_node_id, created_at, reviewed_by, reviewed_at) 
VALUES ('cc1b1e1d-b7e1-4ec4-985b-c89de7d7f1e9', 'c3d8ae81-112c-4fd1-abf6-1d73ff5ea664', 'BP1', 'Literature Literature Family Case-control Gene-specific Clinical Segregation Literature Literature Statistical Gene-specific Segregation.', 0.85, 25, 'Page 40, Column Left', 'rejected', 'node_5448', '2020-12-09 00:00:00', NULL, '2020-12-14 00:00:00')
ON CONFLICT (id) DO NOTHING;

INSERT INTO evidence_records (id, document_id, evidence_type, content, confidence_score, source_page, source_position, status, neo4j_node_id, created_at, reviewed_by, reviewed_at) 
VALUES ('5d070dd1-2785-4113-a4b4-395ffafb0c3d', '193e33fd-4913-4d7e-badf-49b1a73e9641', 'BS4', 'Case-control Family Statistical Functional Segregation The Statistical Gene-specific Gene-specific Statistical Clinical Segregation.', 0.53, 13, 'Page 17, Column Left', 'pending', 'node_8914', '2022-05-28 00:00:00', 'e1b5618e-724e-4bf3-9896-32d42897b611', NULL)
ON CONFLICT (id) DO NOTHING;

INSERT INTO evidence_records (id, document_id, evidence_type, content, confidence_score, source_page, source_position, status, neo4j_node_id, created_at, reviewed_by, reviewed_at) 
VALUES ('f7468bba-2e97-40d4-85b9-4c0f8c47205c', '193e33fd-4913-4d7e-badf-49b1a73e9641', 'BS4', 'Clinical Clinical Family Functional Literature Statistical Literature Family Literature The Clinical Family.', 0.75, 25, 'Page 2, Column Right', 'rejected', 'node_3566', '2022-06-06 00:00:00', '4821a68e-c9fb-46aa-8b3d-ad33eb86967b', NULL)
ON CONFLICT (id) DO NOTHING;

INSERT INTO evidence_records (id, document_id, evidence_type, content, confidence_score, source_page, source_position, status, neo4j_node_id, created_at, reviewed_by, reviewed_at) 
VALUES ('bb711701-17ce-4485-a242-c366d02fdcd8', '193e33fd-4913-4d7e-badf-49b1a73e9641', 'PP4', 'Case-control Gene-specific Segregation Case-control Family Segregation Segregation Computational Family Statistical Computational Computational.', 0.77, 31, 'Page 26, Column Left', 'approved', 'node_6192', '2022-06-13 00:00:00', 'b6a3eda7-5d70-4db7-a748-33cad2c84a94', NULL)
ON CONFLICT (id) DO NOTHING;

INSERT INTO evidence_records (id, document_id, evidence_type, content, confidence_score, source_page, source_position, status, neo4j_node_id, created_at, reviewed_by, reviewed_at) 
VALUES ('72791aa4-834d-4f9f-8a9f-791da563836d', '193e33fd-4913-4d7e-badf-49b1a73e9641', 'BP2', 'Family Statistical Literature Computational Statistical The Case-control Segregation Statistical Family Family Gene-specific.', 0.96, 44, 'Page 21, Column Left', 'pending', 'node_7103', '2022-05-31 00:00:00', NULL, NULL)
ON CONFLICT (id) DO NOTHING;

INSERT INTO evidence_records (id, document_id, evidence_type, content, confidence_score, source_page, source_position, status, neo4j_node_id, created_at, reviewed_by, reviewed_at) 
VALUES ('c5605443-a1e4-425d-910f-34aa718b70c5', '193e33fd-4913-4d7e-badf-49b1a73e9641', 'BP2', 'Family Statistical The Functional Clinical Gene-specific Clinical The Computational Gene-specific Family Statistical.', 0.92, 11, 'Page 14, Column Left', 'pending', 'node_8892', '2022-05-17 00:00:00', '45381851-fd83-4e92-bb1b-9442a6b62911', NULL)
ON CONFLICT (id) DO NOTHING;

INSERT INTO evidence_records (id, document_id, evidence_type, content, confidence_score, source_page, source_position, status, neo4j_node_id, created_at, reviewed_by, reviewed_at) 
VALUES ('bbcf5ebc-e66d-4d19-a59e-64b32c33ab55', 'bf2ecaaa-f46f-461b-897f-6976dd2e1565', 'PP5', 'Clinical Gene-specific Literature Family Gene-specific Gene-specific Case-control Gene-specific Clinical Case-control Computational Gene-specific.', 0.91, 49, 'Page 7, Column Left', 'rejected', 'node_1362', '2024-05-24 00:00:00', NULL, NULL)
ON CONFLICT (id) DO NOTHING;

INSERT INTO evidence_records (id, document_id, evidence_type, content, confidence_score, source_page, source_position, status, neo4j_node_id, created_at, reviewed_by, reviewed_at) 
VALUES ('5dc6af37-1a1d-41ec-b5ac-3742bde3d2c9', 'bf2ecaaa-f46f-461b-897f-6976dd2e1565', 'BP7', 'The Functional Clinical Clinical Family Clinical Computational Functional Computational Literature Computational Functional.', 0.65, 13, 'Page 46, Column Left', 'rejected', 'node_3893', '2024-05-18 00:00:00', NULL, '2024-05-24 00:00:00')
ON CONFLICT (id) DO NOTHING;

INSERT INTO evidence_records (id, document_id, evidence_type, content, confidence_score, source_page, source_position, status, neo4j_node_id, created_at, reviewed_by, reviewed_at) 
VALUES ('4fa229e2-8477-4f8f-be08-077fca1d792d', 'bf2ecaaa-f46f-461b-897f-6976dd2e1565', 'PP4', 'The Family Statistical Functional Clinical Clinical Gene-specific Gene-specific Family Case-control Statistical Statistical.', 0.91, 16, 'Page 21, Column Right', 'rejected', 'node_7679', '2024-05-15 00:00:00', NULL, NULL)
ON CONFLICT (id) DO NOTHING;

INSERT INTO evidence_records (id, document_id, evidence_type, content, confidence_score, source_page, source_position, status, neo4j_node_id, created_at, reviewed_by, reviewed_at) 
VALUES ('bf7b4435-9bb8-47da-9b0e-80e1f5f490cf', 'bf2ecaaa-f46f-461b-897f-6976dd2e1565', 'BS4', 'Computational Segregation Clinical Gene-specific Functional Computational Computational Clinical Family Gene-specific Computational Literature.', 0.75, 10, 'Page 14, Column Right', 'rejected', 'node_9311', '2024-05-21 00:00:00', NULL, NULL)
ON CONFLICT (id) DO NOTHING;

INSERT INTO evidence_records (id, document_id, evidence_type, content, confidence_score, source_page, source_position, status, neo4j_node_id, created_at, reviewed_by, reviewed_at) 
VALUES ('aa639151-3074-497e-be06-1786ddbb7237', 'bf2ecaaa-f46f-461b-897f-6976dd2e1565', 'BP6', 'Family Segregation Segregation Clinical Family Computational Gene-specific Family Statistical Statistical Segregation Family.', 0.84, 4, 'Page 2, Column Left', 'rejected', 'node_1090', '2024-05-30 00:00:00', '0b1deee6-496a-46f8-ac34-2b58109afbb9', '2024-06-06 00:00:00')
ON CONFLICT (id) DO NOTHING;

INSERT INTO evidence_records (id, document_id, evidence_type, content, confidence_score, source_page, source_position, status, neo4j_node_id, created_at, reviewed_by, reviewed_at) 
VALUES ('79e36141-0ffd-4647-8fee-db3884b66520', 'a2aedd41-a6fc-450a-8275-add28a1d156b', 'PM1', 'Segregation Case-control Computational Computational The Case-control Case-control Literature Family Statistical Statistical The.', 0.93, 5, 'Page 12, Column Right', 'pending', 'node_9634', '2024-01-07 00:00:00', NULL, NULL)
ON CONFLICT (id) DO NOTHING;

INSERT INTO evidence_records (id, document_id, evidence_type, content, confidence_score, source_page, source_position, status, neo4j_node_id, created_at, reviewed_by, reviewed_at) 
VALUES ('acc6412c-a813-4caa-806c-aeaddc7d917e', 'a2aedd41-a6fc-450a-8275-add28a1d156b', 'PP1', 'Gene-specific Clinical Statistical Literature Functional Statistical Family Segregation Functional Functional Literature Case-control.', 0.98, 50, 'Page 32, Column Left', 'approved', 'node_2786', '2024-01-21 00:00:00', NULL, NULL)
ON CONFLICT (id) DO NOTHING;

INSERT INTO evidence_records (id, document_id, evidence_type, content, confidence_score, source_page, source_position, status, neo4j_node_id, created_at, reviewed_by, reviewed_at) 
VALUES ('82a54555-f6d5-430a-b9c1-a9c879dcd0d2', 'a2aedd41-a6fc-450a-8275-add28a1d156b', 'BS1', 'Functional Family Statistical Family Computational Family Literature The Literature Segregation Statistical The.', 0.95, 14, 'Page 27, Column Left', 'pending', 'node_4126', '2023-12-31 00:00:00', NULL, NULL)
ON CONFLICT (id) DO NOTHING;

INSERT INTO evidence_records (id, document_id, evidence_type, content, confidence_score, source_page, source_position, status, neo4j_node_id, created_at, reviewed_by, reviewed_at) 
VALUES ('66c6d72c-5375-47aa-9bf3-386013a8b778', 'a2aedd41-a6fc-450a-8275-add28a1d156b', 'PM5', 'Statistical Gene-specific Segregation Statistical Segregation Case-control Segregation The Case-control Segregation Computational Statistical.', 0.65, 30, 'Page 11, Column Left', 'approved', 'node_3293', '2024-01-18 00:00:00', NULL, NULL)
ON CONFLICT (id) DO NOTHING;

INSERT INTO evidence_records (id, document_id, evidence_type, content, confidence_score, source_page, source_position, status, neo4j_node_id, created_at, reviewed_by, reviewed_at) 
VALUES ('ec80c1ba-f776-4f26-b465-f5068924a7fb', 'a2aedd41-a6fc-450a-8275-add28a1d156b', 'PM4', 'Literature Gene-specific Statistical Case-control Gene-specific Gene-specific Segregation Functional Segregation Clinical Family Case-control.', 0.92, 37, 'Page 16, Column Right', 'approved', 'node_8747', '2024-01-05 00:00:00', 'db37501e-c04e-4dda-90ac-24e22c7c52b8', NULL)
ON CONFLICT (id) DO NOTHING;

INSERT INTO evidence_records (id, document_id, evidence_type, content, confidence_score, source_page, source_position, status, neo4j_node_id, created_at, reviewed_by, reviewed_at) 
VALUES ('87ec792b-17d0-46f2-99ce-9b6022a2ac2f', '47e1f687-abee-436e-b798-09eb876f76ac', 'BP7', 'Clinical Gene-specific Gene-specific Family Gene-specific Functional The Segregation Literature The Literature Computational.', 0.72, 50, 'Page 30, Column Left', 'approved', 'node_9741', '2023-04-19 00:00:00', NULL, '2023-04-23 00:00:00')
ON CONFLICT (id) DO NOTHING;

INSERT INTO evidence_records (id, document_id, evidence_type, content, confidence_score, source_page, source_position, status, neo4j_node_id, created_at, reviewed_by, reviewed_at) 
VALUES ('9b0d8ff6-4246-4a1a-8b69-032b93c5f6e6', '47e1f687-abee-436e-b798-09eb876f76ac', 'PS3', 'Gene-specific Case-control Computational Literature Family The Computational Gene-specific Literature Computational Segregation Computational.', 0.98, 20, 'Page 28, Column Left', 'approved', 'node_9952', '2023-04-09 00:00:00', NULL, '2023-04-14 00:00:00')
ON CONFLICT (id) DO NOTHING;

INSERT INTO evidence_records (id, document_id, evidence_type, content, confidence_score, source_page, source_position, status, neo4j_node_id, created_at, reviewed_by, reviewed_at) 
VALUES ('cec4547e-0af9-4387-bf9c-135b970b3e71', '47e1f687-abee-436e-b798-09eb876f76ac', 'BP5', 'Functional Segregation Case-control Segregation Statistical Clinical Functional Case-control Functional Family Functional Functional.', 0.89, 13, 'Page 35, Column Left', 'rejected', 'node_5435', '2023-04-09 00:00:00', NULL, NULL)
ON CONFLICT (id) DO NOTHING;

INSERT INTO evidence_records (id, document_id, evidence_type, content, confidence_score, source_page, source_position, status, neo4j_node_id, created_at, reviewed_by, reviewed_at) 
VALUES ('6cd7dc21-b7be-4544-ae83-56bd74330ae4', '47e1f687-abee-436e-b798-09eb876f76ac', 'BS3', 'Statistical Segregation Computational Literature Family Gene-specific Statistical Computational Computational Case-control Family Functional.', 0.76, 47, 'Page 40, Column Left', 'pending', 'node_8155', '2023-04-11 00:00:00', NULL, NULL)
ON CONFLICT (id) DO NOTHING;

INSERT INTO evidence_records (id, document_id, evidence_type, content, confidence_score, source_page, source_position, status, neo4j_node_id, created_at, reviewed_by, reviewed_at) 
VALUES ('ba9f512a-9e9a-4222-b696-e77b421fe2cc', '47e1f687-abee-436e-b798-09eb876f76ac', 'PS3', 'Clinical Case-control Literature Family The Clinical Case-control Case-control Segregation Case-control Computational Statistical.', 0.8, 9, 'Page 18, Column Left', 'pending', 'node_9330', '2023-04-20 00:00:00', NULL, NULL)
ON CONFLICT (id) DO NOTHING;

INSERT INTO evidence_records (id, document_id, evidence_type, content, confidence_score, source_page, source_position, status, neo4j_node_id, created_at, reviewed_by, reviewed_at) 
VALUES ('be314ebe-35e6-4587-8c39-1333d8e542d1', '76874fc1-2833-4af7-aa80-29bab2d134b6', 'BS1', 'Functional Family The Literature Clinical Clinical Case-control Functional Computational Family Statistical Clinical.', 0.97, 32, 'Page 16, Column Left', 'rejected', 'node_2132', '2022-02-07 00:00:00', NULL, '2022-02-14 00:00:00')
ON CONFLICT (id) DO NOTHING;

INSERT INTO evidence_records (id, document_id, evidence_type, content, confidence_score, source_page, source_position, status, neo4j_node_id, created_at, reviewed_by, reviewed_at) 
VALUES ('12cdb3db-1aff-4f09-8a74-eedb1d809e4d', '76874fc1-2833-4af7-aa80-29bab2d134b6', 'BP6', 'Case-control Literature Segregation Literature Case-control Gene-specific Case-control Clinical The Clinical Family Gene-specific.', 0.54, 35, 'Page 24, Column Right', 'approved', 'node_9973', '2022-02-26 00:00:00', NULL, NULL)
ON CONFLICT (id) DO NOTHING;

INSERT INTO evidence_records (id, document_id, evidence_type, content, confidence_score, source_page, source_position, status, neo4j_node_id, created_at, reviewed_by, reviewed_at) 
VALUES ('e0cbe396-9286-4b40-9aeb-2ffd9024fcb2', '76874fc1-2833-4af7-aa80-29bab2d134b6', 'PP5', 'The The Clinical Clinical Statistical Gene-specific Family Segregation Clinical Gene-specific Computational Segregation.', 0.54, 44, 'Page 14, Column Right', 'approved', 'node_5463', '2022-02-14 00:00:00', NULL, NULL)
ON CONFLICT (id) DO NOTHING;

INSERT INTO evidence_records (id, document_id, evidence_type, content, confidence_score, source_page, source_position, status, neo4j_node_id, created_at, reviewed_by, reviewed_at) 
VALUES ('280d5371-4e00-40cc-b661-cc54b22bffac', '76874fc1-2833-4af7-aa80-29bab2d134b6', 'PS1', 'Computational Computational Case-control The The Case-control The Statistical Segregation The Clinical Segregation.', 0.54, 30, 'Page 15, Column Left', 'approved', 'node_3596', '2022-02-17 00:00:00', 'a7447f00-a1e6-4f4c-afaa-5c6a67a44858', NULL)
ON CONFLICT (id) DO NOTHING;

INSERT INTO evidence_records (id, document_id, evidence_type, content, confidence_score, source_page, source_position, status, neo4j_node_id, created_at, reviewed_by, reviewed_at) 
VALUES ('3e7a4bc8-6369-4a31-acee-ed856d31ae52', '76874fc1-2833-4af7-aa80-29bab2d134b6', 'PM5', 'Gene-specific Family Functional Clinical Segregation Clinical The Functional Case-control Gene-specific Functional Segregation.', 0.53, 37, 'Page 22, Column Left', 'approved', 'node_5562', '2022-02-21 00:00:00', 'd2637c93-8078-4121-b201-7b63a4f4a0f6', '2022-02-26 00:00:00')
ON CONFLICT (id) DO NOTHING;

INSERT INTO evidence_records (id, document_id, evidence_type, content, confidence_score, source_page, source_position, status, neo4j_node_id, created_at, reviewed_by, reviewed_at) 
VALUES ('7a0ff12c-4bad-496e-830f-5ec5cb9517fc', '45cc4067-057c-43ab-8207-c3fc5004c960', 'PM3', 'Statistical Family Gene-specific Functional Clinical Case-control The Segregation Literature Computational Computational Segregation.', 0.75, 9, 'Page 37, Column Left', 'approved', 'node_8931', '2020-10-13 00:00:00', NULL, '2020-10-17 00:00:00')
ON CONFLICT (id) DO NOTHING;

INSERT INTO evidence_records (id, document_id, evidence_type, content, confidence_score, source_page, source_position, status, neo4j_node_id, created_at, reviewed_by, reviewed_at) 
VALUES ('409e4c58-217f-46c3-8a3d-78e1a045d826', '45cc4067-057c-43ab-8207-c3fc5004c960', 'BP3', 'Case-control Case-control Gene-specific Gene-specific The Gene-specific Case-control Clinical Family Segregation Segregation Family.', 0.98, 37, 'Page 40, Column Right', 'pending', 'node_8329', '2020-10-17 00:00:00', '13c05e41-6efe-4215-aa78-e2cfafb44436', NULL)
ON CONFLICT (id) DO NOTHING;

INSERT INTO evidence_records (id, document_id, evidence_type, content, confidence_score, source_page, source_position, status, neo4j_node_id, created_at, reviewed_by, reviewed_at) 
VALUES ('0a448fd6-0b46-4321-8698-ebb29b3cb1fb', '45cc4067-057c-43ab-8207-c3fc5004c960', 'BS4', 'Segregation The Clinical Family Family The Family Literature Case-control Family Gene-specific Segregation.', 0.73, 20, 'Page 33, Column Left', 'approved', 'node_6596', '2020-10-12 00:00:00', 'c72779cc-52ee-46e4-b3f2-1fa0d73ff9a1', '2020-10-19 00:00:00')
ON CONFLICT (id) DO NOTHING;

INSERT INTO evidence_records (id, document_id, evidence_type, content, confidence_score, source_page, source_position, status, neo4j_node_id, created_at, reviewed_by, reviewed_at) 
VALUES ('c2e2a709-e2fa-4d47-bf1d-6ecada786261', '45cc4067-057c-43ab-8207-c3fc5004c960', 'PP4', 'Statistical Case-control Functional Clinical Family Statistical Segregation Statistical Literature Clinical The Clinical.', 0.72, 50, 'Page 3, Column Left', 'pending', 'node_5656', '2020-10-31 00:00:00', 'd3808937-1b21-402f-a1ed-5c0c7973d293', '2020-11-01 00:00:00')
ON CONFLICT (id) DO NOTHING;

INSERT INTO evidence_records (id, document_id, evidence_type, content, confidence_score, source_page, source_position, status, neo4j_node_id, created_at, reviewed_by, reviewed_at) 
VALUES ('d0596d68-251a-4730-a942-5e36b8d0a9d8', '45cc4067-057c-43ab-8207-c3fc5004c960', 'BP4', 'Statistical Segregation Segregation Segregation Functional Computational The Statistical Statistical Case-control Functional Gene-specific.', 0.55, 35, 'Page 8, Column Right', 'rejected', 'node_9359', '2020-10-26 00:00:00', NULL, NULL)
ON CONFLICT (id) DO NOTHING;

INSERT INTO evidence_records (id, document_id, evidence_type, content, confidence_score, source_page, source_position, status, neo4j_node_id, created_at, reviewed_by, reviewed_at) 
VALUES ('f501d77c-7cd0-4665-996b-4331b7728d6d', 'b221b811-166a-4c90-a8cf-d7614ff50a02', 'PP5', 'Clinical Clinical Segregation The Literature Literature Functional Segregation Family Clinical Gene-specific Clinical.', 0.62, 19, 'Page 7, Column Left', 'rejected', 'node_5677', '2020-03-09 00:00:00', NULL, NULL)
ON CONFLICT (id) DO NOTHING;

INSERT INTO evidence_records (id, document_id, evidence_type, content, confidence_score, source_page, source_position, status, neo4j_node_id, created_at, reviewed_by, reviewed_at) 
VALUES ('af18550a-853e-4728-96d4-6b6ce29c6a80', 'b221b811-166a-4c90-a8cf-d7614ff50a02', 'PP1', 'Computational Literature Gene-specific The Gene-specific Family Segregation Family Statistical The Computational Case-control.', 0.88, 12, 'Page 32, Column Right', 'approved', 'node_9443', '2020-03-11 00:00:00', NULL, NULL)
ON CONFLICT (id) DO NOTHING;

INSERT INTO evidence_records (id, document_id, evidence_type, content, confidence_score, source_page, source_position, status, neo4j_node_id, created_at, reviewed_by, reviewed_at) 
VALUES ('94ef0075-b8f6-4e14-ade4-bba4906d3d38', 'b221b811-166a-4c90-a8cf-d7614ff50a02', 'BS3', 'Clinical Family Case-control Case-control The Case-control Statistical Computational Clinical Functional Segregation Clinical.', 0.82, 7, 'Page 26, Column Left', 'rejected', 'node_3612', '2020-03-13 00:00:00', NULL, NULL)
ON CONFLICT (id) DO NOTHING;

INSERT INTO evidence_records (id, document_id, evidence_type, content, confidence_score, source_page, source_position, status, neo4j_node_id, created_at, reviewed_by, reviewed_at) 
VALUES ('7c566965-1ee2-4897-9253-b14ffe67bba0', 'b221b811-166a-4c90-a8cf-d7614ff50a02', 'PM4', 'Gene-specific Case-control Segregation Family Literature Family Statistical Segregation Statistical Clinical The Clinical.', 0.79, 13, 'Page 45, Column Right', 'approved', 'node_1577', '2020-03-07 00:00:00', NULL, NULL)
ON CONFLICT (id) DO NOTHING;

INSERT INTO evidence_records (id, document_id, evidence_type, content, confidence_score, source_page, source_position, status, neo4j_node_id, created_at, reviewed_by, reviewed_at) 
VALUES ('4ea1cde4-5cf6-4599-97f9-3eb07ecccdf1', 'b221b811-166a-4c90-a8cf-d7614ff50a02', 'PP3', 'Segregation The Clinical Literature Clinical Gene-specific The Case-control Literature Functional Literature Functional.', 0.64, 26, 'Page 5, Column Left', 'rejected', 'node_1893', '2020-04-02 00:00:00', NULL, NULL)
ON CONFLICT (id) DO NOTHING;

INSERT INTO evidence_records (id, document_id, evidence_type, content, confidence_score, source_page, source_position, status, neo4j_node_id, created_at, reviewed_by, reviewed_at) 
VALUES ('b2de5371-683c-4e61-86a8-f3b8b3eb543e', '83d52161-c973-43a4-8bf1-50e3bf91b4c0', 'BP2', 'Statistical Statistical Family Statistical Case-control Functional Computational Computational Literature Case-control Statistical Case-control.', 0.52, 17, 'Page 15, Column Left', 'pending', 'node_3160', '2024-10-22 00:00:00', NULL, '2024-10-25 00:00:00')
ON CONFLICT (id) DO NOTHING;

INSERT INTO evidence_records (id, document_id, evidence_type, content, confidence_score, source_page, source_position, status, neo4j_node_id, created_at, reviewed_by, reviewed_at) 
VALUES ('49a86a9e-a6f8-48e8-b84b-702c7caedf46', '83d52161-c973-43a4-8bf1-50e3bf91b4c0', 'BP1', 'Case-control Functional Functional Clinical Gene-specific Case-control Gene-specific Case-control Segregation Statistical Statistical Statistical.', 0.68, 21, 'Page 5, Column Right', 'pending', 'node_7942', '2024-10-26 00:00:00', NULL, NULL)
ON CONFLICT (id) DO NOTHING;

INSERT INTO evidence_records (id, document_id, evidence_type, content, confidence_score, source_page, source_position, status, neo4j_node_id, created_at, reviewed_by, reviewed_at) 
VALUES ('5da44da5-a324-456a-8ffa-e23d1a882ea3', '83d52161-c973-43a4-8bf1-50e3bf91b4c0', 'PM5', 'The Statistical Segregation Case-control Family Case-control Literature Clinical Clinical Clinical Family Functional.', 0.81, 36, 'Page 4, Column Right', 'approved', 'node_4425', '2024-11-10 00:00:00', NULL, NULL)
ON CONFLICT (id) DO NOTHING;

INSERT INTO evidence_records (id, document_id, evidence_type, content, confidence_score, source_page, source_position, status, neo4j_node_id, created_at, reviewed_by, reviewed_at) 
VALUES ('07e79b68-9df4-4c2b-a671-c5f4de405239', '83d52161-c973-43a4-8bf1-50e3bf91b4c0', 'BP5', 'Clinical The Statistical Functional Clinical Clinical Clinical Segregation Literature Computational Functional Case-control.', 0.6, 41, 'Page 25, Column Right', 'pending', 'node_4971', '2024-11-10 00:00:00', NULL, NULL)
ON CONFLICT (id) DO NOTHING;

INSERT INTO evidence_records (id, document_id, evidence_type, content, confidence_score, source_page, source_position, status, neo4j_node_id, created_at, reviewed_by, reviewed_at) 
VALUES ('91f90b55-6c33-47dc-8753-4fb8565499a8', '83d52161-c973-43a4-8bf1-50e3bf91b4c0', 'BP3', 'Clinical Literature Clinical The Gene-specific Literature Gene-specific Family Literature Functional Literature Clinical.', 0.78, 6, 'Page 35, Column Right', 'rejected', 'node_5032', '2024-11-07 00:00:00', NULL, NULL)
ON CONFLICT (id) DO NOTHING;

INSERT INTO evidence_records (id, document_id, evidence_type, content, confidence_score, source_page, source_position, status, neo4j_node_id, created_at, reviewed_by, reviewed_at) 
VALUES ('bdbf0aec-f639-4db7-ab6f-91fccd156fdc', '2deb31c1-2992-4ef6-82a6-6418f1d97a47', 'BS2', 'The Computational Clinical Functional Functional Segregation The Literature Clinical Gene-specific Literature The.', 0.9, 44, 'Page 30, Column Left', 'approved', 'node_7045', '2023-10-10 00:00:00', NULL, NULL)
ON CONFLICT (id) DO NOTHING;

INSERT INTO evidence_records (id, document_id, evidence_type, content, confidence_score, source_page, source_position, status, neo4j_node_id, created_at, reviewed_by, reviewed_at) 
VALUES ('79c2af34-4181-4240-913c-d6432b9b1180', '2deb31c1-2992-4ef6-82a6-6418f1d97a47', 'PP4', 'Computational Clinical Literature Computational Family Gene-specific Gene-specific Gene-specific Family Segregation Segregation Segregation.', 0.58, 39, 'Page 22, Column Right', 'approved', 'node_1626', '2023-10-09 00:00:00', NULL, NULL)
ON CONFLICT (id) DO NOTHING;

INSERT INTO evidence_records (id, document_id, evidence_type, content, confidence_score, source_page, source_position, status, neo4j_node_id, created_at, reviewed_by, reviewed_at) 
VALUES ('e3e6e425-9308-4ad2-baf5-0a62a45d7baa', '2deb31c1-2992-4ef6-82a6-6418f1d97a47', 'BA1', 'Case-control Computational Clinical Functional Literature Statistical Family Segregation Literature Case-control Clinical Statistical.', 0.82, 4, 'Page 31, Column Left', 'rejected', 'node_3893', '2023-10-17 00:00:00', NULL, '2023-10-24 00:00:00')
ON CONFLICT (id) DO NOTHING;

INSERT INTO evidence_records (id, document_id, evidence_type, content, confidence_score, source_page, source_position, status, neo4j_node_id, created_at, reviewed_by, reviewed_at) 
VALUES ('4f95a972-ce3f-45b9-83f3-9d3b9142f174', '2deb31c1-2992-4ef6-82a6-6418f1d97a47', 'BA1', 'Family Statistical The Gene-specific Case-control Case-control The Functional Functional Functional Clinical Statistical.', 0.55, 50, 'Page 23, Column Right', 'rejected', 'node_7632', '2023-10-21 00:00:00', NULL, NULL)
ON CONFLICT (id) DO NOTHING;

INSERT INTO evidence_records (id, document_id, evidence_type, content, confidence_score, source_page, source_position, status, neo4j_node_id, created_at, reviewed_by, reviewed_at) 
VALUES ('4768f639-71da-48f1-b9f7-0885d70da488', '2deb31c1-2992-4ef6-82a6-6418f1d97a47', 'BS4', 'Segregation Case-control Gene-specific Family Case-control Segregation The Computational Statistical Case-control Gene-specific The.', 0.95, 44, 'Page 1, Column Left', 'approved', 'node_1668', '2023-10-12 00:00:00', NULL, NULL)
ON CONFLICT (id) DO NOTHING;

INSERT INTO evidence_records (id, document_id, evidence_type, content, confidence_score, source_page, source_position, status, neo4j_node_id, created_at, reviewed_by, reviewed_at) 
VALUES ('7a22a6de-cffe-498d-8652-70f77132db7d', 'c56bc782-12ed-4aa0-ad19-d25982bd284e', 'BS2', 'The The The The Family Statistical The Case-control Case-control Segregation Family Gene-specific.', 0.86, 43, 'Page 47, Column Left', 'pending', 'node_5461', '2022-01-29 00:00:00', '8632484e-aa26-40b5-8a23-4a84a95a0157', '2022-02-04 00:00:00')
ON CONFLICT (id) DO NOTHING;

INSERT INTO evidence_records (id, document_id, evidence_type, content, confidence_score, source_page, source_position, status, neo4j_node_id, created_at, reviewed_by, reviewed_at) 
VALUES ('ee29085b-976b-495e-ab91-9363e1fdf69b', 'c56bc782-12ed-4aa0-ad19-d25982bd284e', 'PP3', 'Segregation Gene-specific Statistical Statistical Literature Case-control Gene-specific Statistical Family Gene-specific The Family.', 0.83, 20, 'Page 5, Column Right', 'rejected', 'node_9076', '2022-01-24 00:00:00', NULL, NULL)
ON CONFLICT (id) DO NOTHING;

INSERT INTO evidence_records (id, document_id, evidence_type, content, confidence_score, source_page, source_position, status, neo4j_node_id, created_at, reviewed_by, reviewed_at) 
VALUES ('0afff266-e3c0-4968-97ac-f855db1e0829', 'c56bc782-12ed-4aa0-ad19-d25982bd284e', 'PM5', 'Computational Statistical Gene-specific Segregation Computational The Gene-specific Gene-specific Functional Clinical Case-control Functional.', 0.52, 25, 'Page 43, Column Right', 'rejected', 'node_4848', '2022-01-29 00:00:00', NULL, NULL)
ON CONFLICT (id) DO NOTHING;

INSERT INTO evidence_records (id, document_id, evidence_type, content, confidence_score, source_page, source_position, status, neo4j_node_id, created_at, reviewed_by, reviewed_at) 
VALUES ('d51d9ad2-70bc-4676-ae74-9bdc41679511', 'c56bc782-12ed-4aa0-ad19-d25982bd284e', 'PM1', 'Statistical Literature Family Gene-specific Gene-specific Statistical Functional Literature Functional Segregation Case-control The.', 0.92, 23, 'Page 43, Column Left', 'pending', 'node_2720', '2022-01-07 00:00:00', '6b7fd2f0-b7c0-4577-8326-3001e198128e', NULL)
ON CONFLICT (id) DO NOTHING;

INSERT INTO evidence_records (id, document_id, evidence_type, content, confidence_score, source_page, source_position, status, neo4j_node_id, created_at, reviewed_by, reviewed_at) 
VALUES ('51842ef8-f440-4659-befe-623037067a7b', 'c56bc782-12ed-4aa0-ad19-d25982bd284e', 'BS4', 'The Functional Clinical Clinical Gene-specific Gene-specific Gene-specific The Functional Literature Segregation Computational.', 0.97, 46, 'Page 12, Column Right', 'rejected', 'node_1481', '2022-01-28 00:00:00', NULL, '2022-01-31 00:00:00')
ON CONFLICT (id) DO NOTHING;

INSERT INTO evidence_records (id, document_id, evidence_type, content, confidence_score, source_page, source_position, status, neo4j_node_id, created_at, reviewed_by, reviewed_at) 
VALUES ('ed358fb8-b66e-45bd-836e-a5a50314528d', 'ca653959-af55-4ee4-bc5b-2509e40b26b8', 'PM3', 'Clinical Family Segregation Segregation Statistical Statistical Segregation Family Family Statistical Case-control Segregation.', 0.62, 25, 'Page 42, Column Left', 'pending', 'node_9148', '2022-05-24 00:00:00', '099f6b1c-79f4-4767-981c-ddc81f72e351', NULL)
ON CONFLICT (id) DO NOTHING;

INSERT INTO evidence_records (id, document_id, evidence_type, content, confidence_score, source_page, source_position, status, neo4j_node_id, created_at, reviewed_by, reviewed_at) 
VALUES ('ae768adb-335e-4b28-8d90-0d269ad920f0', 'ca653959-af55-4ee4-bc5b-2509e40b26b8', 'BP4', 'The Gene-specific Case-control Clinical Segregation Family Literature Gene-specific Case-control Literature The Segregation.', 0.57, 34, 'Page 28, Column Left', 'pending', 'node_7231', '2022-06-03 00:00:00', NULL, '2022-06-07 00:00:00')
ON CONFLICT (id) DO NOTHING;

INSERT INTO evidence_records (id, document_id, evidence_type, content, confidence_score, source_page, source_position, status, neo4j_node_id, created_at, reviewed_by, reviewed_at) 
VALUES ('4890968c-ac3a-41a6-a3db-adb64ad98e49', 'ca653959-af55-4ee4-bc5b-2509e40b26b8', 'BP6', 'Computational Family Computational Clinical Segregation Clinical Statistical Statistical Clinical Statistical Segregation The.', 0.85, 39, 'Page 47, Column Right', 'pending', 'node_8161', '2022-06-01 00:00:00', NULL, '2022-06-06 00:00:00')
ON CONFLICT (id) DO NOTHING;

INSERT INTO evidence_records (id, document_id, evidence_type, content, confidence_score, source_page, source_position, status, neo4j_node_id, created_at, reviewed_by, reviewed_at) 
VALUES ('830c4af5-b554-430b-8a1a-b840b7ba4357', 'ca653959-af55-4ee4-bc5b-2509e40b26b8', 'PM5', 'Computational Functional Literature Clinical Functional Case-control The The Case-control Case-control Gene-specific The.', 0.79, 16, 'Page 3, Column Left', 'rejected', 'node_5817', '2022-05-18 00:00:00', '7510c64c-a8e1-498b-8b27-4e8568377b24', NULL)
ON CONFLICT (id) DO NOTHING;

INSERT INTO evidence_records (id, document_id, evidence_type, content, confidence_score, source_page, source_position, status, neo4j_node_id, created_at, reviewed_by, reviewed_at) 
VALUES ('f4f16439-3f63-4c92-89fa-492f8ccc029e', 'ca653959-af55-4ee4-bc5b-2509e40b26b8', 'PM6', 'Statistical Clinical The Literature Computational Gene-specific Statistical Computational Functional Family Segregation Literature.', 0.94, 47, 'Page 8, Column Right', 'approved', 'node_7976', '2022-05-17 00:00:00', 'a9e89011-115f-4438-b0c7-43c52eb7a17b', NULL)
ON CONFLICT (id) DO NOTHING;

INSERT INTO evidence_records (id, document_id, evidence_type, content, confidence_score, source_page, source_position, status, neo4j_node_id, created_at, reviewed_by, reviewed_at) 
VALUES ('599a1721-ae4e-4dbf-aa26-ae296c8f1636', '91f76c8f-ba40-47f5-b804-f1bd9fafdbe1', 'BP1', 'Statistical Statistical Statistical Literature Gene-specific The Gene-specific Functional Computational The Clinical Segregation.', 0.98, 36, 'Page 2, Column Left', 'rejected', 'node_1763', '2024-12-07 00:00:00', NULL, '2024-12-10 00:00:00')
ON CONFLICT (id) DO NOTHING;

INSERT INTO evidence_records (id, document_id, evidence_type, content, confidence_score, source_page, source_position, status, neo4j_node_id, created_at, reviewed_by, reviewed_at) 
VALUES ('cb88e2a9-2b53-405e-8ea4-7540b0ac68f6', '91f76c8f-ba40-47f5-b804-f1bd9fafdbe1', 'PP1', 'Literature Computational Family Statistical Gene-specific Literature Computational Gene-specific Statistical Family Functional Literature.', 0.95, 22, 'Page 39, Column Left', 'pending', 'node_1545', '2024-12-27 00:00:00', NULL, NULL)
ON CONFLICT (id) DO NOTHING;

INSERT INTO evidence_records (id, document_id, evidence_type, content, confidence_score, source_page, source_position, status, neo4j_node_id, created_at, reviewed_by, reviewed_at) 
VALUES ('ecb6889f-b795-4ac1-9b52-59c5f410fd4a', '91f76c8f-ba40-47f5-b804-f1bd9fafdbe1', 'BA1', 'Gene-specific Clinical Segregation Case-control Segregation Segregation Gene-specific Statistical Literature Computational Computational Literature.', 0.53, 44, 'Page 27, Column Right', 'rejected', 'node_6528', '2024-12-06 00:00:00', 'ba6ffc93-d3ab-473f-9b68-d58ac83803dd', NULL)
ON CONFLICT (id) DO NOTHING;

INSERT INTO evidence_records (id, document_id, evidence_type, content, confidence_score, source_page, source_position, status, neo4j_node_id, created_at, reviewed_by, reviewed_at) 
VALUES ('4a81f177-872b-4677-9951-807918e248b1', '91f76c8f-ba40-47f5-b804-f1bd9fafdbe1', 'PM1', 'The Functional Segregation Statistical Gene-specific Segregation Literature Clinical Statistical Segregation Segregation The.', 0.92, 35, 'Page 3, Column Right', 'rejected', 'node_6603', '2024-12-11 00:00:00', 'd64627e5-6346-4d44-940f-8ea68e50322f', NULL)
ON CONFLICT (id) DO NOTHING;

INSERT INTO evidence_records (id, document_id, evidence_type, content, confidence_score, source_page, source_position, status, neo4j_node_id, created_at, reviewed_by, reviewed_at) 
VALUES ('511a9f8d-0860-41ca-adb6-d02d277d205c', '91f76c8f-ba40-47f5-b804-f1bd9fafdbe1', 'PM4', 'Clinical Family Computational Functional Functional Clinical Functional Gene-specific Gene-specific Literature The Clinical.', 0.84, 6, 'Page 13, Column Right', 'rejected', 'node_7626', '2024-12-02 00:00:00', NULL, '2024-12-04 00:00:00')
ON CONFLICT (id) DO NOTHING;

INSERT INTO evidence_records (id, document_id, evidence_type, content, confidence_score, source_page, source_position, status, neo4j_node_id, created_at, reviewed_by, reviewed_at) 
VALUES ('34f102d5-f120-411c-8aa2-548b6d32a453', '92ecac31-f768-4daf-aafc-b2f8d860900c', 'PP1', 'Computational Segregation Gene-specific Computational Gene-specific Gene-specific Literature Statistical Case-control Clinical Computational Statistical.', 0.9, 21, 'Page 38, Column Left', 'approved', 'node_6459', '2021-11-29 00:00:00', '4bdc591d-8a04-4dfa-b65a-0d6b6ecac46c', NULL)
ON CONFLICT (id) DO NOTHING;

INSERT INTO evidence_records (id, document_id, evidence_type, content, confidence_score, source_page, source_position, status, neo4j_node_id, created_at, reviewed_by, reviewed_at) 
VALUES ('6c04b363-ac3b-48d2-9716-13f2c38e712f', '92ecac31-f768-4daf-aafc-b2f8d860900c', 'BS4', 'Gene-specific Case-control Literature Clinical Statistical The Statistical Case-control Gene-specific Statistical The Case-control.', 0.95, 30, 'Page 28, Column Right', 'pending', 'node_2020', '2021-12-03 00:00:00', '4161e0ac-ae74-4595-a1ea-aa888829ece3', NULL)
ON CONFLICT (id) DO NOTHING;

INSERT INTO evidence_records (id, document_id, evidence_type, content, confidence_score, source_page, source_position, status, neo4j_node_id, created_at, reviewed_by, reviewed_at) 
VALUES ('6c962b97-add5-4d31-b85b-7a8ecadeb53a', '92ecac31-f768-4daf-aafc-b2f8d860900c', 'PP2', 'Statistical Gene-specific Segregation Statistical Literature Gene-specific Family Case-control Literature Literature Family The.', 0.72, 43, 'Page 27, Column Right', 'rejected', 'node_2647', '2021-12-06 00:00:00', '131dda60-05fa-4f72-89d0-5a92c52aaff8', '2021-12-12 00:00:00')
ON CONFLICT (id) DO NOTHING;

INSERT INTO evidence_records (id, document_id, evidence_type, content, confidence_score, source_page, source_position, status, neo4j_node_id, created_at, reviewed_by, reviewed_at) 
VALUES ('bb78e30d-37dc-4ad3-b19a-6b5abc8c01ca', '92ecac31-f768-4daf-aafc-b2f8d860900c', 'BS4', 'The Functional Gene-specific Segregation Statistical Statistical Statistical Literature Family Clinical Case-control Literature.', 0.99, 11, 'Page 30, Column Right', 'approved', 'node_9968', '2021-12-17 00:00:00', '1aa344ed-c160-47da-89a2-f343452e423d', '2021-12-20 00:00:00')
ON CONFLICT (id) DO NOTHING;

INSERT INTO evidence_records (id, document_id, evidence_type, content, confidence_score, source_page, source_position, status, neo4j_node_id, created_at, reviewed_by, reviewed_at) 
VALUES ('592976c7-b170-4ef4-8e9b-cca90516139b', '92ecac31-f768-4daf-aafc-b2f8d860900c', 'BP2', 'Literature Segregation The Case-control Clinical Statistical Statistical Family Literature Segregation Gene-specific Clinical.', 0.87, 28, 'Page 2, Column Right', 'approved', 'node_2190', '2021-12-13 00:00:00', NULL, NULL)
ON CONFLICT (id) DO NOTHING;

INSERT INTO evidence_records (id, document_id, evidence_type, content, confidence_score, source_page, source_position, status, neo4j_node_id, created_at, reviewed_by, reviewed_at) 
VALUES ('b1ecbf1d-b964-4337-8632-3249d19ed14c', '36e30111-098d-4c89-a978-65b3845b506e', 'PS2', 'Statistical Segregation The Statistical The Family Family Functional Computational Functional Case-control Segregation.', 0.84, 4, 'Page 9, Column Right', 'pending', 'node_8943', '2023-07-18 00:00:00', NULL, '2023-07-24 00:00:00')
ON CONFLICT (id) DO NOTHING;

INSERT INTO evidence_records (id, document_id, evidence_type, content, confidence_score, source_page, source_position, status, neo4j_node_id, created_at, reviewed_by, reviewed_at) 
VALUES ('e839736c-75c7-448c-9596-46660c3ee490', '36e30111-098d-4c89-a978-65b3845b506e', 'BA1', 'The The Segregation Clinical Functional Case-control Literature Clinical Gene-specific The Functional Statistical.', 0.88, 50, 'Page 15, Column Right', 'approved', 'node_1539', '2023-07-22 00:00:00', 'c261fed4-f22e-469f-842e-a149521b5191', NULL)
ON CONFLICT (id) DO NOTHING;

INSERT INTO evidence_records (id, document_id, evidence_type, content, confidence_score, source_page, source_position, status, neo4j_node_id, created_at, reviewed_by, reviewed_at) 
VALUES ('c2585a64-22dc-4227-b95e-f047c58db052', '36e30111-098d-4c89-a978-65b3845b506e', 'PP1', 'Computational Case-control Segregation Segregation Functional Clinical Statistical The Clinical Segregation Case-control Clinical.', 0.9, 34, 'Page 4, Column Right', 'pending', 'node_2175', '2023-08-01 00:00:00', NULL, NULL)
ON CONFLICT (id) DO NOTHING;

INSERT INTO evidence_records (id, document_id, evidence_type, content, confidence_score, source_page, source_position, status, neo4j_node_id, created_at, reviewed_by, reviewed_at) 
VALUES ('596bf5eb-34da-43e1-ac83-ec3e347385b8', '36e30111-098d-4c89-a978-65b3845b506e', 'PM3', 'Functional Case-control Case-control Statistical Statistical Case-control Gene-specific Family Clinical Computational Literature Statistical.', 0.73, 38, 'Page 42, Column Left', 'approved', 'node_7468', '2023-07-16 00:00:00', NULL, '2023-07-17 00:00:00')
ON CONFLICT (id) DO NOTHING;

INSERT INTO evidence_records (id, document_id, evidence_type, content, confidence_score, source_page, source_position, status, neo4j_node_id, created_at, reviewed_by, reviewed_at) 
VALUES ('2515ca5e-76f7-4e30-9c2c-7bdd18fe4d80', '36e30111-098d-4c89-a978-65b3845b506e', 'PP3', 'Case-control Case-control Functional Segregation Gene-specific Statistical Literature The The Literature Statistical Gene-specific.', 0.91, 3, 'Page 39, Column Left', 'approved', 'node_9744', '2023-08-04 00:00:00', '6746c7b4-7fa2-4284-944e-2dae82c3e581', NULL)
ON CONFLICT (id) DO NOTHING;

INSERT INTO evidence_records (id, document_id, evidence_type, content, confidence_score, source_page, source_position, status, neo4j_node_id, created_at, reviewed_by, reviewed_at) 
VALUES ('41ac8e8d-5245-498a-a3ed-a2b5c1bf8b4a', 'bfb28449-cc13-4ac4-bf98-17e6a0d2cc9e', 'BA1', 'Family The The Functional Statistical Case-control Statistical Gene-specific Computational Clinical Computational Statistical.', 0.93, 42, 'Page 9, Column Left', 'pending', 'node_2241', '2021-01-02 00:00:00', '80e6659b-83af-48d5-92d1-3e4b3d69d31e', NULL)
ON CONFLICT (id) DO NOTHING;

INSERT INTO evidence_records (id, document_id, evidence_type, content, confidence_score, source_page, source_position, status, neo4j_node_id, created_at, reviewed_by, reviewed_at) 
VALUES ('1c2f88c2-7676-42f6-8cf4-53aa56557040', 'bfb28449-cc13-4ac4-bf98-17e6a0d2cc9e', 'PM6', 'Computational Clinical Segregation Segregation Segregation Functional Functional Segregation Functional Case-control Functional Family.', 0.63, 5, 'Page 38, Column Left', 'rejected', 'node_7199', '2020-12-25 00:00:00', NULL, NULL)
ON CONFLICT (id) DO NOTHING;

INSERT INTO evidence_records (id, document_id, evidence_type, content, confidence_score, source_page, source_position, status, neo4j_node_id, created_at, reviewed_by, reviewed_at) 
VALUES ('31768ff1-b9c6-4067-a20f-0a89187c3b69', 'bfb28449-cc13-4ac4-bf98-17e6a0d2cc9e', 'BS1', 'Functional Gene-specific Gene-specific Statistical The Clinical Case-control Clinical Clinical The Gene-specific Segregation.', 0.57, 10, 'Page 20, Column Right', 'rejected', 'node_4328', '2020-12-15 00:00:00', NULL, NULL)
ON CONFLICT (id) DO NOTHING;

INSERT INTO evidence_records (id, document_id, evidence_type, content, confidence_score, source_page, source_position, status, neo4j_node_id, created_at, reviewed_by, reviewed_at) 
VALUES ('704f5c42-f03d-42d6-8162-adf3af5b0744', 'bfb28449-cc13-4ac4-bf98-17e6a0d2cc9e', 'BS2', 'Family The Literature Clinical Clinical The Functional Clinical Gene-specific Gene-specific Family The.', 0.99, 50, 'Page 21, Column Left', 'pending', 'node_4651', '2021-01-02 00:00:00', NULL, '2021-01-08 00:00:00')
ON CONFLICT (id) DO NOTHING;

INSERT INTO evidence_records (id, document_id, evidence_type, content, confidence_score, source_page, source_position, status, neo4j_node_id, created_at, reviewed_by, reviewed_at) 
VALUES ('a9b2738c-d10b-41a0-b944-3fe602590857', 'bfb28449-cc13-4ac4-bf98-17e6a0d2cc9e', 'PP3', 'Case-control Case-control Clinical Segregation Literature Case-control Statistical Literature Functional The Computational Functional.', 0.61, 27, 'Page 7, Column Left', 'pending', 'node_8361', '2020-12-31 00:00:00', NULL, '2021-01-04 00:00:00')
ON CONFLICT (id) DO NOTHING;

INSERT INTO evidence_records (id, document_id, evidence_type, content, confidence_score, source_page, source_position, status, neo4j_node_id, created_at, reviewed_by, reviewed_at) 
VALUES ('1d4f7d05-b229-4b6d-9bd2-11fa377ba461', '0c9b6fd1-3f5d-47ac-883a-cd21ce5a02b6', 'PP3', 'Computational Gene-specific Clinical Family Computational Segregation Statistical Family Segregation Family The Case-control.', 0.72, 43, 'Page 14, Column Right', 'approved', 'node_6411', '2020-03-02 00:00:00', NULL, NULL)
ON CONFLICT (id) DO NOTHING;

INSERT INTO evidence_records (id, document_id, evidence_type, content, confidence_score, source_page, source_position, status, neo4j_node_id, created_at, reviewed_by, reviewed_at) 
VALUES ('3ca4c760-7b25-44be-b1dd-14a59583a8e8', '0c9b6fd1-3f5d-47ac-883a-cd21ce5a02b6', 'BS4', 'Literature Literature Computational Case-control The Literature The Functional Case-control Segregation Gene-specific Computational.', 0.67, 44, 'Page 44, Column Left', 'pending', 'node_5087', '2020-03-18 00:00:00', NULL, NULL)
ON CONFLICT (id) DO NOTHING;

INSERT INTO evidence_records (id, document_id, evidence_type, content, confidence_score, source_page, source_position, status, neo4j_node_id, created_at, reviewed_by, reviewed_at) 
VALUES ('424ac9e1-ad41-4ce0-ad0d-409d53a371f9', '0c9b6fd1-3f5d-47ac-883a-cd21ce5a02b6', 'PP3', 'Gene-specific Literature Segregation Case-control Functional Statistical Literature Segregation Segregation The Case-control Case-control.', 0.55, 46, 'Page 36, Column Right', 'rejected', 'node_2906', '2020-03-10 00:00:00', NULL, '2020-03-14 00:00:00')
ON CONFLICT (id) DO NOTHING;

INSERT INTO evidence_records (id, document_id, evidence_type, content, confidence_score, source_page, source_position, status, neo4j_node_id, created_at, reviewed_by, reviewed_at) 
VALUES ('d7c03687-430c-4ab3-962a-b3d40b9e9a1a', '0c9b6fd1-3f5d-47ac-883a-cd21ce5a02b6', 'BS2', 'Gene-specific The Segregation Clinical Functional The Statistical Segregation Computational Gene-specific The Family.', 0.77, 32, 'Page 18, Column Right', 'pending', 'node_4165', '2020-03-18 00:00:00', '721e62f1-1a04-4562-8c0a-1e04889c5fd2', '2020-03-24 00:00:00')
ON CONFLICT (id) DO NOTHING;

INSERT INTO evidence_records (id, document_id, evidence_type, content, confidence_score, source_page, source_position, status, neo4j_node_id, created_at, reviewed_by, reviewed_at) 
VALUES ('48aa0afd-c001-49dc-ade5-4b68091fc3b4', '0c9b6fd1-3f5d-47ac-883a-cd21ce5a02b6', 'PP4', 'Family Clinical Literature Functional Statistical Family Family Case-control Case-control Case-control Segregation Functional.', 0.82, 15, 'Page 36, Column Right', 'approved', 'node_5133', '2020-03-13 00:00:00', NULL, '2020-03-17 00:00:00')
ON CONFLICT (id) DO NOTHING;

INSERT INTO evidence_records (id, document_id, evidence_type, content, confidence_score, source_page, source_position, status, neo4j_node_id, created_at, reviewed_by, reviewed_at) 
VALUES ('eee52f2a-adae-4ebd-99ee-0566fc71c2d2', 'f525a3d4-2690-49b6-ac1a-c0b39a47faec', 'BP3', 'Case-control Computational Family Literature Functional Family Gene-specific Functional Clinical Functional Family Family.', 0.79, 36, 'Page 32, Column Right', 'rejected', 'node_9725', '2022-04-03 00:00:00', NULL, '2022-04-04 00:00:00')
ON CONFLICT (id) DO NOTHING;

INSERT INTO evidence_records (id, document_id, evidence_type, content, confidence_score, source_page, source_position, status, neo4j_node_id, created_at, reviewed_by, reviewed_at) 
VALUES ('81d70bf0-bd45-4ff2-9045-7a8e4b135b69', 'f525a3d4-2690-49b6-ac1a-c0b39a47faec', 'BA1', 'The Clinical Segregation Case-control Literature Statistical The Literature Family The Family Gene-specific.', 0.54, 14, 'Page 21, Column Left', 'rejected', 'node_6992', '2022-03-26 00:00:00', NULL, NULL)
ON CONFLICT (id) DO NOTHING;

INSERT INTO evidence_records (id, document_id, evidence_type, content, confidence_score, source_page, source_position, status, neo4j_node_id, created_at, reviewed_by, reviewed_at) 
VALUES ('467db1c5-34b1-4d41-b108-76142595805e', 'f525a3d4-2690-49b6-ac1a-c0b39a47faec', 'BP2', 'Clinical Literature Gene-specific Segregation Gene-specific Segregation Literature Clinical Gene-specific Functional Family Clinical.', 0.69, 31, 'Page 9, Column Left', 'rejected', 'node_2747', '2022-03-22 00:00:00', '7b6a057b-ba09-423a-95f1-38ce4dc47d17', '2022-03-23 00:00:00')
ON CONFLICT (id) DO NOTHING;

INSERT INTO evidence_records (id, document_id, evidence_type, content, confidence_score, source_page, source_position, status, neo4j_node_id, created_at, reviewed_by, reviewed_at) 
VALUES ('eb895455-2559-4a69-8f2b-cf9f753f42e8', 'f525a3d4-2690-49b6-ac1a-c0b39a47faec', 'BP5', 'The The Literature The Computational Family Case-control Clinical Functional Computational Segregation Family.', 0.83, 48, 'Page 44, Column Left', 'pending', 'node_9264', '2022-03-23 00:00:00', 'c947e74e-c739-440a-81b3-8d534ec08cd3', NULL)
ON CONFLICT (id) DO NOTHING;

INSERT INTO evidence_records (id, document_id, evidence_type, content, confidence_score, source_page, source_position, status, neo4j_node_id, created_at, reviewed_by, reviewed_at) 
VALUES ('76acf4d0-244a-4640-bbe9-d955fba70218', 'f525a3d4-2690-49b6-ac1a-c0b39a47faec', 'PM1', 'Functional Literature Segregation The Gene-specific The Literature Gene-specific Clinical Family Clinical The.', 0.8, 31, 'Page 20, Column Right', 'approved', 'node_2105', '2022-03-29 00:00:00', NULL, NULL)
ON CONFLICT (id) DO NOTHING;

INSERT INTO evidence_records (id, document_id, evidence_type, content, confidence_score, source_page, source_position, status, neo4j_node_id, created_at, reviewed_by, reviewed_at) 
VALUES ('02b36148-8b05-4fd3-9c45-db1707103322', 'ca2fd067-0f87-4d28-b59a-9ff07eb92f10', 'BP1', 'Clinical Gene-specific Clinical Family Clinical Functional Clinical Computational Gene-specific Family Clinical Segregation.', 0.98, 24, 'Page 46, Column Left', 'rejected', 'node_8036', '2023-03-16 00:00:00', NULL, NULL)
ON CONFLICT (id) DO NOTHING;

INSERT INTO evidence_records (id, document_id, evidence_type, content, confidence_score, source_page, source_position, status, neo4j_node_id, created_at, reviewed_by, reviewed_at) 
VALUES ('3e41c096-d57f-4590-8f89-6c7843ad61e5', 'ca2fd067-0f87-4d28-b59a-9ff07eb92f10', 'BP2', 'Segregation The Segregation Literature Clinical Computational Clinical Literature Statistical Family Gene-specific Statistical.', 0.93, 37, 'Page 20, Column Right', 'rejected', 'node_6094', '2023-03-06 00:00:00', NULL, '2023-03-10 00:00:00')
ON CONFLICT (id) DO NOTHING;

INSERT INTO evidence_records (id, document_id, evidence_type, content, confidence_score, source_page, source_position, status, neo4j_node_id, created_at, reviewed_by, reviewed_at) 
VALUES ('b03d7ba6-3f1b-4d2f-a3d5-58d19345da01', 'ca2fd067-0f87-4d28-b59a-9ff07eb92f10', 'BA1', 'Case-control Clinical Clinical Case-control Case-control The The Segregation Statistical Gene-specific Clinical Family.', 0.79, 45, 'Page 35, Column Left', 'pending', 'node_3423', '2023-03-03 00:00:00', NULL, NULL)
ON CONFLICT (id) DO NOTHING;

INSERT INTO evidence_records (id, document_id, evidence_type, content, confidence_score, source_page, source_position, status, neo4j_node_id, created_at, reviewed_by, reviewed_at) 
VALUES ('88f7b05d-c099-45ec-9fb7-af0ec5a47879', 'ca2fd067-0f87-4d28-b59a-9ff07eb92f10', 'PM4', 'Computational Functional Literature Literature Segregation Case-control Literature Computational The Clinical Clinical Clinical.', 0.9, 17, 'Page 23, Column Right', 'approved', 'node_3696', '2023-03-12 00:00:00', NULL, NULL)
ON CONFLICT (id) DO NOTHING;

INSERT INTO evidence_records (id, document_id, evidence_type, content, confidence_score, source_page, source_position, status, neo4j_node_id, created_at, reviewed_by, reviewed_at) 
VALUES ('cb76ea20-6010-443a-9ae2-ef7acb40e6e8', 'ca2fd067-0f87-4d28-b59a-9ff07eb92f10', 'PP4', 'Segregation Family The Segregation Computational Family Functional Segregation Statistical Statistical Literature Literature.', 0.8, 47, 'Page 41, Column Left', 'approved', 'node_3684', '2023-03-17 00:00:00', NULL, '2023-03-18 00:00:00')
ON CONFLICT (id) DO NOTHING;

INSERT INTO evidence_records (id, document_id, evidence_type, content, confidence_score, source_page, source_position, status, neo4j_node_id, created_at, reviewed_by, reviewed_at) 
VALUES ('762a7864-2c7e-4e4d-9d42-ba69a42d08b2', '8be9310a-fa84-48e7-8212-3dfce053f8b6', 'PM1', 'Segregation The Statistical Literature Gene-specific Gene-specific Statistical Clinical Case-control Gene-specific Family Family.', 0.87, 30, 'Page 42, Column Left', 'rejected', 'node_8036', '2024-03-05 00:00:00', NULL, '2024-03-12 00:00:00')
ON CONFLICT (id) DO NOTHING;

INSERT INTO evidence_records (id, document_id, evidence_type, content, confidence_score, source_page, source_position, status, neo4j_node_id, created_at, reviewed_by, reviewed_at) 
VALUES ('57343438-7404-4ce6-ab73-0a1af1ba5259', '8be9310a-fa84-48e7-8212-3dfce053f8b6', 'PS1', 'Family Case-control Clinical Gene-specific Literature Clinical Clinical Clinical Segregation Statistical Literature Computational.', 0.56, 47, 'Page 11, Column Right', 'approved', 'node_5411', '2024-02-26 00:00:00', NULL, NULL)
ON CONFLICT (id) DO NOTHING;

INSERT INTO evidence_records (id, document_id, evidence_type, content, confidence_score, source_page, source_position, status, neo4j_node_id, created_at, reviewed_by, reviewed_at) 
VALUES ('5adb4ced-d7e8-4e8b-b429-328cafa67d1e', '8be9310a-fa84-48e7-8212-3dfce053f8b6', 'BS4', 'Clinical Clinical Gene-specific Literature Case-control Statistical Segregation Case-control The Literature Computational Functional.', 0.55, 49, 'Page 16, Column Right', 'approved', 'node_3289', '2024-03-05 00:00:00', NULL, NULL)
ON CONFLICT (id) DO NOTHING;

INSERT INTO evidence_records (id, document_id, evidence_type, content, confidence_score, source_page, source_position, status, neo4j_node_id, created_at, reviewed_by, reviewed_at) 
VALUES ('62a63db5-a897-44d8-a13c-c605430f151a', '8be9310a-fa84-48e7-8212-3dfce053f8b6', 'PM4', 'Clinical Statistical Segregation The Statistical Statistical Clinical Family Segregation Computational Segregation The.', 0.87, 8, 'Page 3, Column Right', 'rejected', 'node_2277', '2024-02-23 00:00:00', NULL, '2024-02-24 00:00:00')
ON CONFLICT (id) DO NOTHING;

INSERT INTO evidence_records (id, document_id, evidence_type, content, confidence_score, source_page, source_position, status, neo4j_node_id, created_at, reviewed_by, reviewed_at) 
VALUES ('a2647c09-37f4-4b67-895a-3643f15a407c', '8be9310a-fa84-48e7-8212-3dfce053f8b6', 'BP2', 'Clinical Gene-specific Family The Family Segregation Gene-specific Segregation Computational Clinical Clinical Computational.', 0.99, 35, 'Page 25, Column Left', 'pending', 'node_3811', '2024-03-08 00:00:00', NULL, NULL)
ON CONFLICT (id) DO NOTHING;

INSERT INTO agent_logs (id, task_id, agent_type, input_hash, output, duration_ms, retry_count, created_at) 
VALUES ('d4be8040-ae3d-4c96-a18d-e3b0e7134fc8', '6eafb0ff-bcbc-4251-9303-e7c0ac81e4ec', 'extraction', 'c76ebd60fe3fa223b65adbecae1c9ed6dab0e1e30bf4cbaf06dca6709b6541de', '{"operation": "extract", "result": "success", "details": {"processed_pages": 4, "entities_found": 8, "confidence_avg": 0.75}}', 4198, 2, '2020-12-08 20:29:00')
ON CONFLICT (id) DO NOTHING;

INSERT INTO agent_logs (id, task_id, agent_type, input_hash, output, duration_ms, retry_count, created_at) 
VALUES ('0756ec8d-59c2-48f4-b4c1-18803e507f43', '6eafb0ff-bcbc-4251-9303-e7c0ac81e4ec', 'layout', 'be73241c8538c1e82d8472ca2d77756f20afe2a7f1b0d2305194e97a87d95450', '{"operation": "parse", "result": "success", "details": {"processed_pages": 17, "entities_found": 10, "confidence_avg": 0.65}}', 3009, 3, '2020-12-08 20:56:00')
ON CONFLICT (id) DO NOTHING;

INSERT INTO agent_logs (id, task_id, agent_type, input_hash, output, duration_ms, retry_count, created_at) 
VALUES ('d78ec912-b3ae-4e38-bc8f-6e94332f07c2', '456981fc-eac4-41a6-867a-12a5f1e9059e', 'translation', '0a231766846a24ca53ac9c1302a7c1d7e61fd5c39e003ecb4ef28afa21ae8215', '{"operation": "classify", "result": "success", "details": {"processed_pages": 4, "entities_found": 8, "confidence_avg": 0.87}}', 2052, 1, '2022-05-16 09:17:00')
ON CONFLICT (id) DO NOTHING;

INSERT INTO agent_logs (id, task_id, agent_type, input_hash, output, duration_ms, retry_count, created_at) 
VALUES ('c2167902-cf97-483e-9b15-7b9734b457c1', '456981fc-eac4-41a6-867a-12a5f1e9059e', 'classification', '2167ff3eaf48375d006e39b58d4f8fad0d8e2186f2c16757264c5e72f970b219', '{"operation": "classify", "result": "success", "details": {"processed_pages": 3, "entities_found": 14, "confidence_avg": 0.91}}', 3270, 3, '2022-05-16 09:10:00')
ON CONFLICT (id) DO NOTHING;

INSERT INTO agent_logs (id, task_id, agent_type, input_hash, output, duration_ms, retry_count, created_at) 
VALUES ('a3f97ce7-c438-4552-86b6-0e6aad0526b4', '718ffc96-293d-4814-9c26-d1a92987b84e', 'validation', 'ec3868171477e9cb5a8151329ecf1d6562bb4fada7226982a103a16dd0afb896', '{"operation": "classify", "result": "success", "details": {"processed_pages": 10, "entities_found": 11, "confidence_avg": 0.7}}', 820, 2, '2024-05-13 04:05:00')
ON CONFLICT (id) DO NOTHING;

INSERT INTO agent_logs (id, task_id, agent_type, input_hash, output, duration_ms, retry_count, created_at) 
VALUES ('f9f48b97-261e-451d-b844-c84da175dd56', '718ffc96-293d-4814-9c26-d1a92987b84e', 'classification', '7cc91e94079ed6fc8d5026c61ea129923a5c7a73e0c0f812aa2efbb545356ece', '{"operation": "parse", "result": "success", "details": {"processed_pages": 3, "entities_found": 13, "confidence_avg": 0.71}}', 2734, 2, '2024-05-13 04:07:00')
ON CONFLICT (id) DO NOTHING;

INSERT INTO agent_logs (id, task_id, agent_type, input_hash, output, duration_ms, retry_count, created_at) 
VALUES ('da48f536-c694-4c06-8471-bc3798c16531', '29298603-2469-4ebb-bb9f-211025ff7673', 'extraction', '230156421143ee4ee2344c747564dfda084fb1f0ed7b24095786e2578bbbc9fc', '{"operation": "classify", "result": "success", "details": {"processed_pages": 20, "entities_found": 5, "confidence_avg": 0.62}}', 2731, 2, '2023-12-22 05:11:00')
ON CONFLICT (id) DO NOTHING;

INSERT INTO agent_logs (id, task_id, agent_type, input_hash, output, duration_ms, retry_count, created_at) 
VALUES ('ba2cc855-9a56-48b5-a54d-f4f14c13d2a3', '29298603-2469-4ebb-bb9f-211025ff7673', 'extraction', '479e2dc4c8fda87d514c6cc7042c96081946ada418bdf64fa34cdfe3240dfedb', '{"operation": "extract", "result": "success", "details": {"processed_pages": 4, "entities_found": 6, "confidence_avg": 0.61}}', 4670, 0, '2023-12-22 05:41:00')
ON CONFLICT (id) DO NOTHING;

INSERT INTO agent_logs (id, task_id, agent_type, input_hash, output, duration_ms, retry_count, created_at) 
VALUES ('4bb1c527-bb16-4803-9b15-cb23256883bb', '6c64ebd5-3050-49da-8689-de1f7627f15f', 'layout', '7338a791714e629529966c6be5e0831b363a99a75dc6e36e4a186691eecd0c41', '{"operation": "validate", "result": "success", "details": {"processed_pages": 4, "entities_found": 3, "confidence_avg": 0.72}}', 2698, 2, '2023-04-06 15:22:00')
ON CONFLICT (id) DO NOTHING;

INSERT INTO agent_logs (id, task_id, agent_type, input_hash, output, duration_ms, retry_count, created_at) 
VALUES ('62647785-3af2-40a6-9bb7-a0bea989eab8', '6c64ebd5-3050-49da-8689-de1f7627f15f', 'extraction', '409cf470ad757d57d3e9bdf2b25005805ffc6e52185865430a41a088ecdd37aa', '{"operation": "parse", "result": "success", "details": {"processed_pages": 13, "entities_found": 7, "confidence_avg": 0.86}}', 4971, 1, '2023-04-06 15:33:00')
ON CONFLICT (id) DO NOTHING;

INSERT INTO agent_logs (id, task_id, agent_type, input_hash, output, duration_ms, retry_count, created_at) 
VALUES ('89577eff-f8ac-4354-ac2c-66cc3144da6c', 'cff52dbf-c2f4-4087-94f2-85669572951e', 'translation', '9c7bda78f745a3b358b0c1d8486d949ae88a571490d7f9194e82f719e8dac0df', '{"operation": "extract", "result": "success", "details": {"processed_pages": 10, "entities_found": 14, "confidence_avg": 0.69}}', 3880, 1, '2022-01-27 08:31:00')
ON CONFLICT (id) DO NOTHING;

INSERT INTO agent_logs (id, task_id, agent_type, input_hash, output, duration_ms, retry_count, created_at) 
VALUES ('e0a66b4c-8c30-4859-a54d-90fff32c2a57', 'cff52dbf-c2f4-4087-94f2-85669572951e', 'classification', 'cb6c74db2eac276d9609ad47eacfd354aa8730f334863964957266295976c336', '{"operation": "extract", "result": "success", "details": {"processed_pages": 10, "entities_found": 1, "confidence_avg": 0.92}}', 3738, 2, '2022-01-27 08:54:00')
ON CONFLICT (id) DO NOTHING;

INSERT INTO agent_logs (id, task_id, agent_type, input_hash, output, duration_ms, retry_count, created_at) 
VALUES ('03837285-95cf-4224-b5c3-4ce216937f06', '64442813-0bf1-448d-b8b9-eae96ead9985', 'layout', '6a4c1f7c35fbddafc160dbb809e1b013a162454bd0f6eff028efb039c8af6c23', '{"operation": "extract", "result": "success", "details": {"processed_pages": 8, "entities_found": 11, "confidence_avg": 0.65}}', 281, 3, '2020-10-10 11:21:00')
ON CONFLICT (id) DO NOTHING;

INSERT INTO agent_logs (id, task_id, agent_type, input_hash, output, duration_ms, retry_count, created_at) 
VALUES ('685ec208-733b-44f0-b486-694d8d40217a', '64442813-0bf1-448d-b8b9-eae96ead9985', 'layout', '33c419cd1645e394c12056ffc670d01ce4a2ca0d0fa9d1add835bda0458018ea', '{"operation": "validate", "result": "success", "details": {"processed_pages": 11, "entities_found": 0, "confidence_avg": 0.76}}', 2521, 2, '2020-10-10 11:51:00')
ON CONFLICT (id) DO NOTHING;

INSERT INTO agent_logs (id, task_id, agent_type, input_hash, output, duration_ms, retry_count, created_at) 
VALUES ('a7b986a4-12f8-48e6-bef7-1b4d27e364fb', 'a93ca233-3beb-4c8e-9cfe-2f42cf100584', 'validation', '0c464a26e9a299659235b3e131a4b193fd1a4019cc584c058686777d41fc1afc', '{"operation": "classify", "result": "success", "details": {"processed_pages": 6, "entities_found": 15, "confidence_avg": 0.87}}', 998, 1, '2020-03-06 18:29:00')
ON CONFLICT (id) DO NOTHING;

INSERT INTO agent_logs (id, task_id, agent_type, input_hash, output, duration_ms, retry_count, created_at) 
VALUES ('75c26820-4e75-4759-ae54-133856eaf281', 'a93ca233-3beb-4c8e-9cfe-2f42cf100584', 'validation', '333cda21e9f17d3e9fa41cdddf019dd90d1c5789b41ddfa22b4ea0fc49c98223', '{"operation": "extract", "result": "success", "details": {"processed_pages": 2, "entities_found": 9, "confidence_avg": 0.63}}', 1558, 2, '2020-03-06 18:08:00')
ON CONFLICT (id) DO NOTHING;

INSERT INTO agent_logs (id, task_id, agent_type, input_hash, output, duration_ms, retry_count, created_at) 
VALUES ('16c34ee2-0e2b-4f8f-aa53-9a394b6e8c77', '5af78757-1202-4597-a883-9471fa67535d', 'extraction', '92e5d63866496b644bc7d28d5e1bdaa5dd1fed8ed5f9ebb08debe2a7e1bf917a', '{"operation": "validate", "result": "failed", "details": {"processed_pages": 10, "entities_found": 3, "confidence_avg": 0.81}}', 954, 2, '2024-10-15 05:50:00')
ON CONFLICT (id) DO NOTHING;

INSERT INTO agent_logs (id, task_id, agent_type, input_hash, output, duration_ms, retry_count, created_at) 
VALUES ('0df4ad23-e7ba-4c4a-8c36-9efd70500e3a', '5af78757-1202-4597-a883-9471fa67535d', 'validation', 'aab8ca2623c418949b01c52092c80e94d17d47bc7d6b614cc5eb498d2266dd7e', '{"operation": "parse", "result": "success", "details": {"processed_pages": 18, "entities_found": 10, "confidence_avg": 0.86}}', 1244, 1, '2024-10-15 05:26:00')
ON CONFLICT (id) DO NOTHING;

INSERT INTO agent_logs (id, task_id, agent_type, input_hash, output, duration_ms, retry_count, created_at) 
VALUES ('59cbb12d-09fa-4321-b682-477ff3a472cf', '1124605c-13b3-4a4d-bcac-c06e55f97d3c', 'validation', '7b6bc22d9426b946189adddffeb1561c4ad8c4d9e6fdc1334f4a5bbf914e7255', '{"operation": "classify", "result": "success", "details": {"processed_pages": 8, "entities_found": 4, "confidence_avg": 0.9}}', 1242, 1, '2023-10-06 05:34:00')
ON CONFLICT (id) DO NOTHING;

INSERT INTO agent_logs (id, task_id, agent_type, input_hash, output, duration_ms, retry_count, created_at) 
VALUES ('8994f79f-0a40-410d-96e0-edc9a5b6b7c2', '1124605c-13b3-4a4d-bcac-c06e55f97d3c', 'extraction', '253f05ab50472632c24be2e964d349cc2f475515c8a4c85fad4e0d7e13608b0e', '{"operation": "extract", "result": "success", "details": {"processed_pages": 4, "entities_found": 15, "confidence_avg": 0.76}}', 244, 2, '2023-10-06 05:10:00')
ON CONFLICT (id) DO NOTHING;

INSERT INTO agent_logs (id, task_id, agent_type, input_hash, output, duration_ms, retry_count, created_at) 
VALUES ('5a9d4b59-f93b-4a1c-9cc4-1e0a5856ddbd', '68ab36ba-d68c-45ae-a2e8-b037cea66ecd', 'layout', 'e46a9c498d7c9def3645e1e7df4579f1e408527ccba954f777d7658b1e3de6be', '{"operation": "extract", "result": "success", "details": {"processed_pages": 2, "entities_found": 15, "confidence_avg": 0.81}}', 4496, 3, '2022-01-06 06:38:00')
ON CONFLICT (id) DO NOTHING;

INSERT INTO agent_logs (id, task_id, agent_type, input_hash, output, duration_ms, retry_count, created_at) 
VALUES ('fdc516c9-cb0e-4fb9-887c-e6fd120b8c08', '68ab36ba-d68c-45ae-a2e8-b037cea66ecd', 'translation', '3027923ca8a075f9281d3c3d7eb68b566c143ec24a22e06c8d9328be9b1d12f1', '{"operation": "extract", "result": "success", "details": {"processed_pages": 17, "entities_found": 0, "confidence_avg": 0.82}}', 481, 3, '2022-01-06 06:03:00')
ON CONFLICT (id) DO NOTHING;

INSERT INTO agent_logs (id, task_id, agent_type, input_hash, output, duration_ms, retry_count, created_at) 
VALUES ('3791a486-86d8-4822-b80e-345495db86f0', '47909f2d-d203-4caa-a952-217abe5e229b', 'translation', '4c4cce42a5c82a07b81c50aa53fa5da9734fa378e1e50a930d859a3cbee13b11', '{"operation": "parse", "result": "success", "details": {"processed_pages": 16, "entities_found": 4, "confidence_avg": 0.72}}', 1760, 2, '2022-05-14 17:06:00')
ON CONFLICT (id) DO NOTHING;

INSERT INTO agent_logs (id, task_id, agent_type, input_hash, output, duration_ms, retry_count, created_at) 
VALUES ('1d3f8249-4e7b-4ea0-8474-f13c2b9b2ce9', '47909f2d-d203-4caa-a952-217abe5e229b', 'layout', 'ffe14bf7e6ed82682ce61d671723f28795a1f346a45b2d7868c32f39171833ad', '{"operation": "classify", "result": "success", "details": {"processed_pages": 10, "entities_found": 0, "confidence_avg": 0.66}}', 4418, 0, '2022-05-14 17:34:00')
ON CONFLICT (id) DO NOTHING;

INSERT INTO agent_logs (id, task_id, agent_type, input_hash, output, duration_ms, retry_count, created_at) 
VALUES ('95e58c31-b391-430b-9fc9-7c5e8b659533', 'fa9213de-c90d-47ef-8198-d18aa1b0cfaa', 'classification', '1d76722446bb399704f9b902c7f863e24b51cdd1fbd4957e8473ffb249fc21aa', '{"operation": "extract", "result": "success", "details": {"processed_pages": 20, "entities_found": 10, "confidence_avg": 0.69}}', 525, 0, '2024-11-27 02:26:00')
ON CONFLICT (id) DO NOTHING;

INSERT INTO agent_logs (id, task_id, agent_type, input_hash, output, duration_ms, retry_count, created_at) 
VALUES ('4e9756a9-708b-4461-a767-95439ebaa8cf', 'fa9213de-c90d-47ef-8198-d18aa1b0cfaa', 'translation', '8af03b92509cf803285a6b25d7d1143ff8cc5f91486093ea1367077d03757b48', '{"operation": "extract", "result": "success", "details": {"processed_pages": 5, "entities_found": 5, "confidence_avg": 0.88}}', 3896, 3, '2024-11-27 02:34:00')
ON CONFLICT (id) DO NOTHING;

INSERT INTO agent_logs (id, task_id, agent_type, input_hash, output, duration_ms, retry_count, created_at) 
VALUES ('242b10e6-6b8b-4f41-8edf-0b3c6aaec93c', 'ca481507-eec3-4c7d-8ca7-5f8dc0518981', 'extraction', 'd5e407fe03642705cb3265ca48f3cb529c55f936d3d449e00a73081f222bfac5', '{"operation": "classify", "result": "success", "details": {"processed_pages": 18, "entities_found": 10, "confidence_avg": 0.75}}', 3544, 3, '2021-11-28 05:43:00')
ON CONFLICT (id) DO NOTHING;

INSERT INTO agent_logs (id, task_id, agent_type, input_hash, output, duration_ms, retry_count, created_at) 
VALUES ('5247cd81-4ec1-408b-a14e-db2c5c44eff2', 'ca481507-eec3-4c7d-8ca7-5f8dc0518981', 'layout', '0a89e4630b383c46191c1b61f88a55210683a534673496395f858adbb89a461e', '{"operation": "classify", "result": "success", "details": {"processed_pages": 13, "entities_found": 1, "confidence_avg": 0.77}}', 1372, 0, '2021-11-28 05:07:00')
ON CONFLICT (id) DO NOTHING;

INSERT INTO agent_logs (id, task_id, agent_type, input_hash, output, duration_ms, retry_count, created_at) 
VALUES ('e85cd0bb-f4c6-4630-b91d-cac5e4df0e66', 'f1114ac9-13be-488e-8fa3-eced1e2eaa4f', 'layout', 'f736c6d2a69a3c276b2ec2f84392bd1b3c07caa97910b43bf18df844bd38079e', '{"operation": "validate", "result": "success", "details": {"processed_pages": 7, "entities_found": 8, "confidence_avg": 0.72}}', 4297, 2, '2023-07-12 15:38:00')
ON CONFLICT (id) DO NOTHING;

INSERT INTO agent_logs (id, task_id, agent_type, input_hash, output, duration_ms, retry_count, created_at) 
VALUES ('99475734-1160-4422-9a8c-2c782f8dc5e6', 'f1114ac9-13be-488e-8fa3-eced1e2eaa4f', 'validation', '12e28b1366eec14e44cf40521c828177e802180b611df40e357834a7e64655c1', '{"operation": "extract", "result": "success", "details": {"processed_pages": 14, "entities_found": 0, "confidence_avg": 0.8}}', 2081, 0, '2023-07-12 15:43:00')
ON CONFLICT (id) DO NOTHING;

INSERT INTO agent_logs (id, task_id, agent_type, input_hash, output, duration_ms, retry_count, created_at) 
VALUES ('3b245bc6-b259-4746-939f-616579cc32a5', 'a0273e1c-2dc6-483f-a4a9-259203365a9c', 'extraction', 'b6699f43709ef8b4e25ae6590071348779ffc7bce6d2c1acff27f4a0bb8b4d72', '{"operation": "classify", "result": "success", "details": {"processed_pages": 18, "entities_found": 1, "confidence_avg": 0.65}}', 125, 0, '2020-12-11 01:12:00')
ON CONFLICT (id) DO NOTHING;

INSERT INTO agent_logs (id, task_id, agent_type, input_hash, output, duration_ms, retry_count, created_at) 
VALUES ('b0f03a38-841e-48c8-846e-017292cb0593', 'a0273e1c-2dc6-483f-a4a9-259203365a9c', 'validation', 'e679ee0edd455f00153b5bb639f16b5bd28257d70caf9ffa08c6c3855c4e33c5', '{"operation": "validate", "result": "success", "details": {"processed_pages": 14, "entities_found": 9, "confidence_avg": 0.9}}', 3997, 3, '2020-12-11 01:21:00')
ON CONFLICT (id) DO NOTHING;

INSERT INTO agent_logs (id, task_id, agent_type, input_hash, output, duration_ms, retry_count, created_at) 
VALUES ('e12e9b43-bdd6-4823-bd43-f5d5463e9a8e', 'e7472f56-326e-4bd2-b23c-17fb2cb9b034', 'classification', '51e55ca896d536c8a8ec64a71178d0664b294eaa581bd20d00d77fde1f42f2b7', '{"operation": "validate", "result": "success", "details": {"processed_pages": 11, "entities_found": 5, "confidence_avg": 0.68}}', 243, 3, '2020-03-01 14:29:00')
ON CONFLICT (id) DO NOTHING;

INSERT INTO agent_logs (id, task_id, agent_type, input_hash, output, duration_ms, retry_count, created_at) 
VALUES ('6a7bf411-4b51-419b-ab82-71731a8bb314', 'e7472f56-326e-4bd2-b23c-17fb2cb9b034', 'layout', '79a7b1b5f803345e89f6692f51c8aace4a2baf28a6a26c4de3b9c4988382d451', '{"operation": "parse", "result": "success", "details": {"processed_pages": 15, "entities_found": 12, "confidence_avg": 0.66}}', 1592, 1, '2020-03-01 14:50:00')
ON CONFLICT (id) DO NOTHING;

INSERT INTO agent_logs (id, task_id, agent_type, input_hash, output, duration_ms, retry_count, created_at) 
VALUES ('95ee4d70-6bc8-4b32-83ad-e9aa36acfc35', '65f4bac4-6115-4c05-9732-fe5a2e181956', 'validation', '0e6754dfaffcc1765388b96462d390f17c31f82e3469a93665c0a5f247b045d3', '{"operation": "extract", "result": "success", "details": {"processed_pages": 2, "entities_found": 14, "confidence_avg": 0.71}}', 4629, 2, '2022-03-05 09:35:00')
ON CONFLICT (id) DO NOTHING;

INSERT INTO agent_logs (id, task_id, agent_type, input_hash, output, duration_ms, retry_count, created_at) 
VALUES ('622e3552-dee5-47ff-a0e6-7da5ce2f92ff', '65f4bac4-6115-4c05-9732-fe5a2e181956', 'layout', '6139701a22f6aa6e74bc96b56ba9fcff3f2c1f5ab28c3a34f963cf6b182f2ffa', '{"operation": "extract", "result": "success", "details": {"processed_pages": 6, "entities_found": 0, "confidence_avg": 0.63}}', 4636, 0, '2022-03-05 09:15:00')
ON CONFLICT (id) DO NOTHING;

INSERT INTO agent_logs (id, task_id, agent_type, input_hash, output, duration_ms, retry_count, created_at) 
VALUES ('5619deef-3139-408b-b70d-39e97500ab9c', '3cf42a0d-a040-4ffe-b0a7-73dae1bcd54f', 'translation', '3bf73a9aa6cf5cd3674ebc0b98982ccb3d155c0efb2ac7869c4044748f54ab49', '{"operation": "extract", "result": "success", "details": {"processed_pages": 9, "entities_found": 10, "confidence_avg": 0.77}}', 2936, 2, '2023-02-27 23:52:00')
ON CONFLICT (id) DO NOTHING;

INSERT INTO agent_logs (id, task_id, agent_type, input_hash, output, duration_ms, retry_count, created_at) 
VALUES ('8fe44914-d3b6-4488-8949-c4b85502de56', '3cf42a0d-a040-4ffe-b0a7-73dae1bcd54f', 'extraction', 'fb0274969115effa9c95e0a010392a99961b541467b06b24a591ac6ecb0743e5', '{"operation": "parse", "result": "success", "details": {"processed_pages": 15, "entities_found": 8, "confidence_avg": 0.85}}', 3532, 3, '2023-02-27 23:46:00')
ON CONFLICT (id) DO NOTHING;

INSERT INTO agent_logs (id, task_id, agent_type, input_hash, output, duration_ms, retry_count, created_at) 
VALUES ('92d38437-6760-4dfe-b6e2-5894dd23498e', '8291b44c-1738-46bc-8b5a-006384fa6957', 'validation', '45810d5ed3396272ac6bbe9c6d2d434bfd54faed3ae6598d8606c5e12a9d4774', '{"operation": "validate", "result": "success", "details": {"processed_pages": 19, "entities_found": 5, "confidence_avg": 0.7}}', 1404, 3, '2024-02-14 07:55:00')
ON CONFLICT (id) DO NOTHING;

INSERT INTO agent_logs (id, task_id, agent_type, input_hash, output, duration_ms, retry_count, created_at) 
VALUES ('89f914ba-96c7-4088-8bad-0227bb9fa8c8', '8291b44c-1738-46bc-8b5a-006384fa6957', 'validation', 'f99d8514700fe36e4f02ad50b62479b9a50e3ff257c9dcf530344eab0635a53f', '{"operation": "validate", "result": "success", "details": {"processed_pages": 12, "entities_found": 8, "confidence_avg": 0.94}}', 1703, 3, '2024-02-14 07:42:00')
ON CONFLICT (id) DO NOTHING;
