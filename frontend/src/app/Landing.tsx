"use client";

import Image from "next/image";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { createContext, useContext, useEffect, useState } from "react";
import styles from "./Landing.module.css";

type Language = "pt-BR" | "en";
const LanguageContext = createContext<Language>("en");
const copy = {
  en: {
    nav: "Main navigation", search: "Search companies", docs: "Documentation", key: "Free trial", skip: "Skip to content", contact: "Contact", rights: "All rights reserved.",
    eyebrow: "AMBERN · COMPANY INTELLIGENCE", title: "Discover and assess Brazilian companies.", intro: "Explore companies, understand their business and bring public company data into your decisions. For teams working in Brazil and entering its market.", demo: "Request a demo", available: "Available coverage", brazil: "Brazil", coverage: "Brazil is currently our only available market. Need another country? Tell us where you want to work.", request: "Request country coverage", uses: "From discovery to a better-informed decision.",
    cards: [ ["01", "Prospecting", "Find Brazilian companies by location, economic activity and registration status to identify potential customers and partners."], ["02", "Company assessment", "Review registration details and, depending on your plan, ownership, federal debt and sanctions data to support your assessment."], ["03", "API integration", "Connect company lookups and search to your systems through the REST API. Explore endpoints and authentication in the documentation."] ],
    sourcesTitle: "Know the sources behind your assessment.", sourcesIntro: "Ambern brings together Brazilian public records. Availability varies by source and plan; check the underlying records when making a decision.", sources: [["Receita Federal", "Company registration records: CNPJ identifiers, registration status, economic activities and ownership information."], ["PGFN", "Federal debt registration records from Brazil’s National Treasury Attorney General’s Office."], ["CGU", "Public sanctions records from Brazil’s Office of the Comptroller General."]], premium: "Premium data, including debt, sanctions and ownership details, depends on your plan. A record is an input to your assessment, not a certification of a company’s reliability.", apiTitle: "Company data, in your workflow.", apiText: "Use a key to authenticate your requests. Start with the documentation to choose the endpoints and fields your integration needs.", apiLabel: "Example request · replace CNPJ and API key", start: "Start exploring with Ambern.", startText: "Try the platform for free, or email us to discuss your use case and request a demonstration.", emailNote: "Demo requests are handled by email. Our team will arrange the next steps with you.",
  },
  "pt-BR": {
    nav: "Navegação principal", search: "Buscar empresas", docs: "Documentação", key: "Teste gratuito", skip: "Ir para o conteúdo", contact: "Contato", rights: "Todos os direitos reservados.",
    eyebrow: "AMBERN · INTELIGÊNCIA EMPRESARIAL", title: "Encontre empresas e oportunidades no Brasil.", intro: "Explore empresas, entenda seus negócios e use dados públicos nas suas decisões. Para equipes que atuam no Brasil ou querem entrar nesse mercado.", demo: "Solicitar demonstração", available: "Cobertura disponível", brazil: "Brasil", coverage: "O Brasil é o único mercado disponível no momento. Precisa de outro país? Conte onde você quer atuar.", request: "Solicitar cobertura de outro país", uses: "Da descoberta à decisão bem informada.",
    cards: [["01", "Prospecção", "Encontre empresas brasileiras por localização, atividade econômica e situação cadastral para identificar potenciais clientes e parceiros."], ["02", "Avaliação de empresas", "Consulte dados cadastrais e, conforme seu plano, informações societárias, dívida ativa federal e sanções para apoiar sua avaliação."], ["03", "Integração via API", "Conecte consultas e buscas de empresas aos seus sistemas pela API REST. Explore os endpoints e a autenticação na documentação."]],
    sourcesTitle: "Conheça as fontes da sua análise.", sourcesIntro: "A Ambern reúne registros públicos brasileiros. A disponibilidade varia por fonte e plano; confira os registros de origem ao tomar uma decisão.", sources: [["Receita Federal", "Registros cadastrais de empresas: CNPJ, situação cadastral, atividades econômicas e informações societárias."], ["PGFN", "Registros de dívida ativa da União da Procuradoria-Geral da Fazenda Nacional."], ["CGU", "Registros públicos de sanções da Controladoria-Geral da União."]], premium: "Dados premium, incluindo dívidas, sanções e detalhes societários, dependem do plano. Um registro apoia sua análise e não certifica a confiabilidade de uma empresa.", apiTitle: "Dados empresariais no seu fluxo de trabalho.", apiText: "Use uma chave para autenticar suas requisições. Comece pela documentação para escolher os endpoints e campos necessários à sua integração.", apiLabel: "Exemplo de requisição · substitua o CNPJ e a chave", start: "Comece a explorar com a Ambern.", startText: "Teste a plataforma gratuitamente ou envie um e-mail para conversar sobre seu caso de uso e solicitar uma demonstração.", emailNote: "As demonstrações são solicitadas por e-mail. Nossa equipe combina os próximos passos com você.",
  },
};

export function SiteShell({ children, contactEmail }: { children: React.ReactNode; contactEmail: string }) {
  const [language, setLanguage] = useState<Language>("en");
  const pathname = usePathname();
  useEffect(() => {
    try { const saved = localStorage.getItem("ambern-language"); if (saved === "en" || saved === "pt-BR") setLanguage(saved); } catch { /* Storage is optional. */ }
  }, []);
  useEffect(() => { document.documentElement.lang = language; }, [language]);
  function changeLanguage(next: Language) {
    setLanguage(next);
    try { localStorage.setItem("ambern-language", next); } catch { /* Still works without storage. */ }
  }
  const t = copy[language];
  const logo = <Image src="/assets/ambern-logo.svg" alt="Ambern" width={160} height={39} priority />;
  return <LanguageContext.Provider value={language}>
    <a className={styles.skip} href="#main-content">{t.skip}</a>
    <nav id="site-nav" className={styles.nav} aria-label={t.nav}>
      <Link href="/" aria-label="Ambern">{logo}</Link>
      <div className={styles.navLinks}>
        <Link href="/docs">{t.docs}</Link><Link href="/app/search">{t.search}</Link>
        <Link className={styles.primary} href="/app/keys">{t.key}</Link>
        <div className={styles.languages} role="group" aria-label={language === "en" ? "Language" : "Idioma"}>
          <button type="button" lang="pt-BR" aria-label="Português" aria-pressed={language === "pt-BR"} onClick={() => changeLanguage("pt-BR")}>PT</button>
          <button type="button" lang="en" aria-label="English" aria-pressed={language === "en"} onClick={() => changeLanguage("en")}>EN</button>
        </div>
      </div>
    </nav>
    <main id="main-content" tabIndex={-1} lang={pathname === "/" ? language : "en"}>{children}</main>
    <footer id="site-footer" className={styles.footer}>
      <Link href="/" aria-label="Ambern">{logo}</Link>
      <div><a href={`mailto:${contactEmail}`}>{t.contact}</a><a href="https://ambern.dev" target="_blank" rel="noopener noreferrer">ambern.dev</a></div>
      <p>© {new Date().getFullYear()} Ambern. {t.rights}</p>
    </footer>
  </LanguageContext.Provider>;
}

export default function Landing({ contactEmail }: { contactEmail: string }) {
  const language = useContext(LanguageContext);
  const t = copy[language];
  const demo = `mailto:${contactEmail}?subject=${encodeURIComponent(language === "en" ? "Ambern demo request" : "Solicitação de demonstração Ambern")}`;
  return <div className={styles.landing}>
    <section id="hero" className={styles.hero} aria-labelledby="hero-title">
      <p className={styles.eyebrow}>{t.eyebrow}</p><h1 id="hero-title">{t.title}</h1><p className={styles.intro}>{t.intro}</p>
      <div className={styles.actions}><Link id="cta-get-key" className={styles.primary} href="/app/keys">{t.key} <span aria-hidden="true">↗</span></Link><a className={styles.secondary} href={demo}>{t.demo}</a></div>
      <p className={styles.heroFoot}>{t.available}: <strong>{t.brazil}</strong></p>
    </section>
    <section id="stats-bar" className={styles.coverage} aria-labelledby="coverage-title"><div><p className={styles.eyebrow}>{t.available}</p><h2 id="coverage-title">{t.brazil} <span className={styles.dot} aria-hidden="true" /></h2></div><div><p>{t.coverage}</p><a href={`mailto:${contactEmail}?subject=${encodeURIComponent(language === "en" ? "Country coverage request" : "Solicitação de cobertura de país")}`}>{t.request} <span aria-hidden="true">↗</span></a></div></section>
    <section id="use-cases" className={styles.section} aria-labelledby="uses-title"><h2 id="uses-title">{t.uses}</h2><div className={styles.cards}>{t.cards.map(([number, title, description]) => <article className={styles.card} key={number}><span className={styles.number}>{number}</span><h3>{title}</h3><p>{description}</p></article>)}</div></section>
    <section id="sources" className={styles.sources} aria-labelledby="sources-title"><div><p className={styles.eyebrow}>RECEITA FEDERAL / PGFN / CGU</p><h2 id="sources-title">{t.sourcesTitle}</h2><p>{t.sourcesIntro}</p></div><div>{t.sources.map(([name, description]) => <article className={styles.source} key={name}><h3>{name}</h3><p>{description}</p></article>)}</div><p className={styles.note}>{t.premium}</p></section>
    <section id="api-preview" className={`${styles.section} ${styles.api}`} aria-labelledby="api-title"><div><h2 id="api-title">{t.apiTitle}</h2><p>{t.apiText}</p><Link id="cta-view-docs" href="/docs">{t.docs} <span aria-hidden="true">↗</span></Link></div><div className={styles.code}><p>{t.apiLabel}</p><pre><code>{`curl https://brazil.ambern.dev/v1/company/{CNPJ} \\\n  -H "X-API-Key: YOUR_API_KEY"`}</code></pre></div></section>
    <section id="pricing" className={styles.closing} aria-labelledby="start-title"><h2 id="start-title">{t.start}</h2><p>{t.startText}</p><div className={styles.actions}><Link className={styles.primary} href="/app/keys">{t.key}</Link><a className={styles.secondary} href={demo}>{t.demo}</a></div><p className={styles.small}>{t.emailNote}</p></section>
  </div>;
}
