import type { Dictionaries, Option, Requirement } from '../api/types';

/** Детерминированные фикстуры моков (раздел 5). Math.random() не используется. */

/**
 * Генератор псевдослучайных чисел mulberry32 с фиксированным seed.
 * @param seed начальное значение
 */
export function createRng(seed: number): () => number {
  let a = seed >>> 0;
  return () => {
    a = (a + 0x6d2b79f5) >>> 0;
    let t = a;
    t = Math.imul(t ^ (t >>> 15), t | 1);
    t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

export const SEED_USERS = [
  { id: 'u1', email: 'seeker@example.com', password: 'Password1', role: 'seeker', confirmed: true },
  { id: 'u2', email: 'noresume@example.com', password: 'Password1', role: 'seeker', confirmed: true },
  { id: 'u3', email: 'unconfirmed@example.com', password: 'Password1', role: 'seeker', confirmed: false },
  { id: 'u4', email: 'admin@example.com', password: 'Admin1234', role: 'admin', confirmed: true },
] as const;

export const SKILL_POOL: string[] = [
  'Python', 'SQL', 'PostgreSQL', 'Docker', 'Git', 'FastAPI', 'Linux', 'REST API', 'Django', 'Redis',
  'Pandas', 'NumPy', 'scikit-learn', 'PyTorch', 'Airflow', 'Kafka', 'Celery', 'RabbitMQ', 'Pytest', 'CI/CD',
  'JavaScript', 'TypeScript', 'React', 'HTML', 'CSS', 'Node.js', 'Kubernetes', 'Terraform', 'Ansible', 'Nginx',
  'MongoDB', 'ClickHouse', 'Spark', 'Hadoop', 'Tableau', 'Power BI', 'Excel', '1С', 'Java', 'Spring',
  'Kotlin', 'Swift', 'C#', '.NET', 'Go', 'Rust', 'PHP', 'Laravel', 'Selenium', 'Postman',
  'Jira', 'Agile', 'Scrum', 'UML', 'BPMN', 'Figma', 'Prometheus', 'Grafana', 'ELK', 'GitLab CI',
];

/** Содержимое резюме seeker@example.com (для имитации кросс-энкодера): первые 25 навыков словаря. */
export const SEEKER_SKILLS: string[] = SKILL_POOL.slice(0, 25);

export const REGIONS: Option[] = [
  ['77', 'Москва'], ['78', 'Санкт-Петербург'], ['50', 'Московская область'], ['47', 'Ленинградская область'],
  ['23', 'Краснодарский край'], ['66', 'Свердловская область'], ['16', 'Республика Татарстан'],
  ['52', 'Нижегородская область'], ['54', 'Новосибирская область'], ['63', 'Самарская область'],
  ['61', 'Ростовская область'], ['02', 'Республика Башкортостан'], ['74', 'Челябинская область'],
  ['59', 'Пермский край'], ['24', 'Красноярский край'], ['36', 'Воронежская область'],
  ['34', 'Волгоградская область'], ['55', 'Омская область'], ['72', 'Тюменская область'],
  ['38', 'Иркутская область'], ['42', 'Кемеровская область'], ['25', 'Приморский край'],
  ['27', 'Хабаровский край'], ['26', 'Ставропольский край'], ['64', 'Саратовская область'],
  ['56', 'Оренбургская область'], ['58', 'Пензенская область'], ['73', 'Ульяновская область'],
  ['18', 'Удмуртская республика'], ['21', 'Чувашская республика'], ['12', 'Республика Марий Эл'],
  ['13', 'Республика Мордовия'], ['43', 'Кировская область'], ['76', 'Ярославская область'],
  ['33', 'Владимирская область'], ['37', 'Ивановская область'], ['44', 'Костромская область'],
  ['69', 'Тверская область'], ['71', 'Тульская область'], ['40', 'Калужская область'],
  ['62', 'Рязанская область'], ['48', 'Липецкая область'], ['68', 'Тамбовская область'],
  ['31', 'Белгородская область'], ['46', 'Курская область'], ['57', 'Орловская область'],
  ['32', 'Брянская область'], ['67', 'Смоленская область'], ['35', 'Вологодская область'],
  ['29', 'Архангельская область'], ['51', 'Мурманская область'], ['10', 'Республика Карелия'],
  ['11', 'Республика Коми'], ['53', 'Новгородская область'], ['60', 'Псковская область'],
  ['39', 'Калининградская область'], ['30', 'Астраханская область'], ['08', 'Республика Калмыкия'],
  ['05', 'Республика Дагестан'], ['06', 'Республика Ингушетия'], ['07', 'Кабардино-Балкарская республика'],
  ['09', 'Карачаево-Черкесская республика'], ['15', 'Республика Северная Осетия — Алания'],
  ['20', 'Чеченская республика'], ['01', 'Республика Адыгея'], ['82', 'Республика Крым'],
  ['92', 'Севастополь'], ['04', 'Республика Алтай'], ['22', 'Алтайский край'],
  ['70', 'Томская область'], ['17', 'Республика Тыва'], ['19', 'Республика Хакасия'],
  ['03', 'Республика Бурятия'], ['75', 'Забайкальский край'], ['14', 'Республика Саха (Якутия)'],
  ['28', 'Амурская область'], ['79', 'Еврейская автономная область'], ['41', 'Камчатский край'],
  ['49', 'Магаданская область'], ['65', 'Сахалинская область'], ['45', 'Курганская область'],
  ['86', 'Ханты-Мансийский автономный округ'], ['89', 'Ямало-Ненецкий автономный округ'],
  ['83', 'Ненецкий автономный округ'], ['87', 'Чукотский автономный округ'],
].map(([code, name]) => ({ code, name }));

export const DICTIONARIES: Dictionaries = {
  regions: REGIONS,
  employment_types: [
    { code: 'full', name: 'Полная занятость' },
    { code: 'part', name: 'Частичная занятость' },
    { code: 'project', name: 'Проектная работа' },
    { code: 'internship', name: 'Стажировка' },
  ],
  schedules: [
    { code: 'fullDay', name: 'Полный день' },
    { code: 'shift', name: 'Сменный график' },
    { code: 'flexible', name: 'Гибкий график' },
    { code: 'remote', name: 'Удалённая работа' },
  ],
  experience: [
    { code: 'noExperience', name: 'Без опыта' },
    { code: 'between1And3', name: 'От 1 года до 3 лет' },
    { code: 'between3And6', name: 'От 3 до 6 лет' },
    { code: 'moreThan6', name: 'Более 6 лет' },
  ],
};

export interface SeedVacancy {
  id: string;
  title: string;
  salary_from: number | null;
  salary_to: number | null;
  employer_name: string;
  published_at: string;
  region_code: string;
  employment_type: string;
  schedule: string;
  experience: string;
  is_active: boolean;
  skills: string[];
  source_fields: { label: string; value: string }[];
}

const PROFESSIONS = [
  'Python-разработчик', 'Аналитик данных', 'Инженер по тестированию', 'Frontend-разработчик',
  'DevOps-инженер', 'Системный аналитик', 'Data Scientist', 'Backend-разработчик', 'Администратор баз данных',
  'Менеджер проектов', 'Бизнес-аналитик', 'Разработчик 1С', 'Инженер данных', 'Java-разработчик',
];
const MODIFIERS = ['', ' (middle)', ' (senior)', ' (junior)', ' в команду платформы', ' в финансовый сектор'];
const EMPLOYERS = [
  'ООО «Ромашка»', 'АО «Вектор»', 'ООО «ТехноСфера»', 'ПАО «Северсталь-Инфо»', 'ООО «Дата-Лаб»',
  'АО «ЦифроПром»', 'ООО «Эксперт-Софт»', 'ИП Кузнецов А. В.', 'ООО «Альфа Системы»', 'АО «Телеком-Сервис»',
];
const LONG_TITLE =
  'Ведущий инженер-разработчик программного обеспечения распределённых высоконагруженных информационных систем ' +
  'обработки и анализа больших данных с опытом построения конвейеров машинного обучения';

const REGION_WEIGHTED = ['77', '78', '50', '16', '66', '54', '23', '52'];

/** Дата вида ГГГГ-ММ-ДД на `back` дней раньше базовой (2026-10-10). */
function dateBack(back: number): string {
  const d = new Date(Date.UTC(2026, 9, 10 - back));
  return d.toISOString().slice(0, 10);
}

/** Строит 150 активных и 1 снятую с публикации вакансию. */
function buildVacancies(): SeedVacancy[] {
  const rng = createRng(20261012);
  const pick = <T,>(arr: readonly T[]): T => arr[Math.floor(rng() * arr.length)];
  const result: SeedVacancy[] = [];

  for (let i = 1; i <= 151; i++) {
    const count = 5 + Math.floor(rng() * 6);
    const skills: string[] = [];
    while (skills.length < count) {
      const skill = rng() < 0.08 ? pick(SEEKER_SKILLS) : pick(SKILL_POOL);
      if (!skills.includes(skill)) skills.push(skill);
    }
    if (i === 7) {
      // Вакансия, все требования которой покрыты резюме seeker@example.com.
      skills.splice(0, skills.length, ...SEEKER_SKILLS.slice(0, 6));
    }

    const kind = i % 5;
    const base = 40000 + Math.floor(rng() * 36) * 10000;
    let salary_from: number | null = null;
    let salary_to: number | null = null;
    if (kind === 0) salary_from = base;
    else if (kind === 1) salary_to = base + 30000;
    else if (kind === 2 || kind === 4) {
      salary_from = base;
      salary_to = Math.min(base + 50000, 450000);
    }

    const title = i === 5 ? LONG_TITLE : `${pick(PROFESSIONS)}${pick(MODIFIERS)}`;
    const region_code = rng() < 0.6 ? pick(REGION_WEIGHTED) : pick(REGIONS).code;
    const employment_type = pick(DICTIONARIES.employment_types).code;
    const schedule = pick(DICTIONARIES.schedules).code;
    const experience = pick(DICTIONARIES.experience).code;
    const employer_name = pick(EMPLOYERS);
    const typeName = DICTIONARIES.employment_types.find((o) => o.code === employment_type)?.name ?? '';
    const scheduleName = DICTIONARIES.schedules.find((o) => o.code === schedule)?.name ?? '';
    const expName = DICTIONARIES.experience.find((o) => o.code === experience)?.name ?? '';

    result.push({
      id: String(i),
      title,
      salary_from,
      salary_to,
      employer_name,
      published_at: i === 151 ? '2026-09-01' : dateBack(Math.floor(rng() * 45)),
      region_code,
      employment_type,
      schedule,
      experience,
      is_active: i !== 151,
      skills,
      source_fields: [
        { label: 'Обязанности', value: `Разработка и сопровождение сервисов.\nУчастие в проектировании архитектуры.\nПодготовка технической документации.` },
        { label: 'Требования', value: `Опыт работы: ${expName.toLowerCase()}.\nЗнание: ${skills.join(', ')}.` },
        { label: 'Условия', value: 'Официальное трудоустройство по ТК РФ.\nДобровольное медицинское страхование.' },
        { label: 'Тип занятости', value: typeName },
        { label: 'График работы', value: scheduleName },
        { label: 'Требуемый опыт', value: expName },
        { label: 'Образование', value: 'Высшее или неполное высшее' },
      ],
    });
  }
  return result;
}

export const VACANCIES: SeedVacancy[] = buildVacancies();

const COVERED_QUOTES = [
  (s: string) => `Более 3 лет коммерческой разработки с использованием ${s}`,
  (s: string) => `Ежедневно работаю с ${s}: проектирование, сопровождение, оптимизация`,
  (s: string) => `Внедрил ${s} в команде из 6 человек и подготовил внутреннюю документацию`,
];
const PARTIAL_QUOTES = [
  (s: string) => `Базовое знакомство с ${s} в рамках учебного проекта`,
  (s: string) => `Прошёл онлайн-курс по ${s}, опыта в рабочих проектах пока нет`,
  (s: string) => `Работал со смежными инструментами, ${s} изучаю самостоятельно`,
];

/** Детерминированный хеш строки (для выбора вердикта и шаблона цитаты). */
function hash(text: string): number {
  return [...text].reduce((h, ch) => (Math.imul(h, 31) + ch.charCodeAt(0)) >>> 0, 7);
}

/**
 * Имитирует кросс-энкодер: для каждого требования вакансии — вердикт и фраза резюме, которая его покрывает.
 * Навык есть в резюме → «Покрыто»; иначе примерно каждое третье требование покрыто частично.
 * @param vacancy вакансия
 * @param resumeSkills содержимое резюме (список навыков фикстуры)
 */
export function buildRequirements(vacancy: SeedVacancy, resumeSkills: string[]): Requirement[] {
  const have = new Set(resumeSkills.map((s) => s.toLowerCase()));
  return vacancy.skills.map((text, index) => {
    const h = hash(`${vacancy.id}:${text}`);
    if (have.has(text.toLowerCase())) {
      return { number: index + 1, text, status: 'covered', resume_quote: COVERED_QUOTES[h % 3](text) };
    }
    if (h % 3 === 0) {
      return { number: index + 1, text, status: 'partially_covered', resume_quote: PARTIAL_QUOTES[(h >>> 2) % 3](text) };
    }
    return { number: index + 1, text, status: 'not_covered', resume_quote: null };
  });
}

/**
 * Процент соответствия: покрытое требование даёт 1, частично покрытое — 0,5.
 * @param requirements требования с вердиктами
 */
export function matchPercentOf(requirements: Requirement[]): number {
  if (requirements.length === 0) return 0;
  const score = requirements.reduce((sum, r) => sum + (r.status === 'covered' ? 1 : r.status === 'partially_covered' ? 0.5 : 0), 0);
  return Math.round((score / requirements.length) * 100);
}

/** Идентификаторы вакансий в избранном у seeker@example.com (последняя — снята с публикации). */
export const SEEKER_FAVORITES = [
  { vacancy_id: '3', added_at: '2026-10-08T10:00:00+03:00' },
  { vacancy_id: '12', added_at: '2026-10-09T12:30:00+03:00' },
  { vacancy_id: '151', added_at: '2026-09-02T09:15:00+03:00' },
];
