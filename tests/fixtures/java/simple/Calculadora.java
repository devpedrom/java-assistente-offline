public class Calculadora {
    private int valor;

    public Calculadora(int valor) {
        this.valor = valor;
    }

    public int somar(int outro) {
        return valor + outro;
    }

    public String ecoar(String texto) {
        return texto;
    }
}
